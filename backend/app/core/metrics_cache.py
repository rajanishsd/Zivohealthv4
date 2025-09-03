"""
Redis-based Performance Metrics Cache

Persistent storage for system performance metrics using Redis with
time-series data organization, automatic cleanup, and efficient querying.
"""

import json
import redis
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from app.utils.timezone import now_local, isoformat_now

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics collected"""
    SYSTEM_CPU = "system_cpu"
    SYSTEM_MEMORY = "system_memory"
    SYSTEM_DISK = "system_disk" 
    SYSTEM_NETWORK = "system_network"
    HTTP_REQUEST = "http_request"
    DATABASE_QUERY = "database_query"
    APPLICATION_ERROR = "application_error"
    REDIS_OPERATION = "redis_operation"


@dataclass
class BaseMetric:
    """Base metric data structure"""
    timestamp: str
    metric_type: str
    value: float
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseMetric':
        return cls(**data)


class RedisMetricsCache:
    """Redis-based metrics storage with time-series organization"""
    
    def __init__(self, redis_client: redis.Redis, retention_hours: int = 168):  # 7 days default
        self.redis = redis_client
        self.retention_hours = retention_hours
        self.retention_seconds = retention_hours * 3600
        self.executor = ThreadPoolExecutor(max_workers=2)
        
        # Redis key patterns
        self.SYSTEM_METRICS_KEY = "metrics:system"
        self.HTTP_METRICS_KEY = "metrics:http"
        self.DB_METRICS_KEY = "metrics:database"
        self.HEALTH_KEY = "metrics:health"
        
        # Time series organization
        self.TIMESERIES_PREFIX = "ts:"
        
    async def store_system_metric(self, metric: BaseMetric) -> None:
        """Store system performance metric"""
        try:
            # Create time series key with minute precision for efficient querying
            timestamp = datetime.fromisoformat(metric.timestamp.replace('Z', '+00:00'))
            minute_key = timestamp.strftime('%Y-%m-%d:%H:%M')
            
            ts_key = f"{self.TIMESERIES_PREFIX}{self.SYSTEM_METRICS_KEY}:{metric.metric_type}:{minute_key}"
            
            # Store metric data
            metric_data = {
                'timestamp': metric.timestamp,
                'value': metric.value,
                'metadata': json.dumps(metric.metadata)
            }
            
            # Use sorted set for time-based queries
            score = timestamp.timestamp()
            await self._execute_redis_command(
                'zadd', ts_key, mapping={json.dumps(metric_data): score}
            )
            
            # Set expiration
            await self._execute_redis_command('expire', ts_key, self.retention_seconds)
            
            # Update latest metrics for health checks
            health_key = f"{self.HEALTH_KEY}:{metric.metric_type}"
            await self._execute_redis_command(
                'hset', health_key, mapping={
                    'latest_value': str(metric.value),
                    'latest_timestamp': metric.timestamp,
                    'metadata': json.dumps(metric.metadata)
                }
            )
            await self._execute_redis_command('expire', health_key, self.retention_seconds)
            
        except Exception as e:
            import traceback
            logger.error(f"Error storing system metric: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    async def store_http_metric(self, method: str, endpoint: str, status_code: int, 
                               response_time_ms: float, **kwargs) -> None:
        """Store HTTP request metric"""
        try:
            timestamp = isoformat_now()
            
            metric_data = {
                'timestamp': timestamp,
                'method': method,
                'endpoint': endpoint,
                'status_code': status_code,
                'response_time_ms': response_time_ms,
                **kwargs
            }
            
            # Store in time series
            ts_timestamp = now_local()
            minute_key = ts_timestamp.strftime('%Y-%m-%d:%H:%M')
            ts_key = f"{self.TIMESERIES_PREFIX}{self.HTTP_METRICS_KEY}:{minute_key}"
            
            score = ts_timestamp.timestamp()
            await self._execute_redis_command(
                'zadd', ts_key, mapping={json.dumps(metric_data): score}
            )
            await self._execute_redis_command('expire', ts_key, self.retention_seconds)
            
            # Update counters for quick stats
            stats_key = f"{self.HTTP_METRICS_KEY}:stats"
            await self._execute_redis_command('hincrby', stats_key, 'total_requests', 1)
            
            if status_code >= 400:
                await self._execute_redis_command('hincrby', stats_key, 'error_count', 1)
                
            await self._execute_redis_command('expire', stats_key, self.retention_seconds)
            
        except Exception as e:
            logger.error(f"Error storing HTTP metric: {e}")
    
    async def store_database_metric(self, operation_type: str, duration_ms: float,
                                   table_name: Optional[str] = None, **kwargs) -> None:
        """Store database operation metric"""
        try:
            timestamp = isoformat_now()
            
            metric_data = {
                'timestamp': timestamp,
                'operation_type': operation_type,
                'duration_ms': duration_ms,
                'table_name': table_name,
                **kwargs
            }
            
            # Store in time series
            ts_timestamp = now_local()
            minute_key = ts_timestamp.strftime('%Y-%m-%d:%H:%M')
            ts_key = f"{self.TIMESERIES_PREFIX}{self.DB_METRICS_KEY}:{minute_key}"
            
            score = ts_timestamp.timestamp()
            await self._execute_redis_command(
                'zadd', ts_key, mapping={json.dumps(metric_data): score}
            )
            await self._execute_redis_command('expire', ts_key, self.retention_seconds)
            
        except Exception as e:
            logger.error(f"Error storing database metric: {e}")
    
    async def get_system_metrics(self, metric_type: Optional[str] = None,
                                hours_back: int = 24, limit: int = 1000) -> List[Dict[str, Any]]:
        """Retrieve system metrics"""
        try:
            end_time = now_local()
            start_time = end_time - timedelta(hours=hours_back)
            
            pattern = f"{self.TIMESERIES_PREFIX}{self.SYSTEM_METRICS_KEY}"
            if metric_type:
                pattern += f":{metric_type}:*"
            else:
                pattern += ":*"
            
            # Get all matching keys
            keys = await self._execute_redis_command('keys', pattern)
            
            all_metrics = []
            for key in keys[:50]:  # Limit keys to prevent performance issues
                # Get data from sorted set within time range
                start_score = start_time.timestamp()
                end_score = end_time.timestamp()
                
                data = await self._execute_redis_command(
                    'zrangebyscore', key, start_score, end_score, withscores=True
                )
                
                for item, score in data:
                    try:
                        metric_data = json.loads(item)
                        if 'metadata' in metric_data and isinstance(metric_data['metadata'], str):
                            metric_data['metadata'] = json.loads(metric_data['metadata'])
                        all_metrics.append(metric_data)
                    except json.JSONDecodeError:
                        continue
            
            # Sort by timestamp and limit
            all_metrics.sort(key=lambda x: x['timestamp'])
            return all_metrics[-limit:] if len(all_metrics) > limit else all_metrics
            
        except Exception as e:
            logger.error(f"Error retrieving system metrics: {e}")
            return []
    
    async def get_http_metrics(self, hours_back: int = 24, limit: int = 1000) -> List[Dict[str, Any]]:
        """Retrieve HTTP request metrics"""
        try:
            end_time = now_local()
            start_time = end_time - timedelta(hours=hours_back)
            
            pattern = f"{self.TIMESERIES_PREFIX}{self.HTTP_METRICS_KEY}:*"
            keys = await self._execute_redis_command('keys', pattern)
            
            all_metrics = []
            for key in keys[:50]:  # Limit keys
                start_score = start_time.timestamp()
                end_score = end_time.timestamp()
                
                data = await self._execute_redis_command(
                    'zrangebyscore', key, start_score, end_score, withscores=True
                )
                
                for item, score in data:
                    try:
                        metric_data = json.loads(item)
                        all_metrics.append(metric_data)
                    except json.JSONDecodeError:
                        continue
            
            # Sort by timestamp and limit
            all_metrics.sort(key=lambda x: x['timestamp'])
            return all_metrics[-limit:] if len(all_metrics) > limit else all_metrics
            
        except Exception as e:
            logger.error(f"Error retrieving HTTP metrics: {e}")
            return []
    
    async def get_database_metrics(self, hours_back: int = 24, limit: int = 1000) -> List[Dict[str, Any]]:
        """Retrieve database operation metrics"""
        try:
            end_time = now_local()
            start_time = end_time - timedelta(hours=hours_back)
            
            pattern = f"{self.TIMESERIES_PREFIX}{self.DB_METRICS_KEY}:*"
            keys = await self._execute_redis_command('keys', pattern)
            
            all_metrics = []
            for key in keys[:50]:  # Limit keys
                start_score = start_time.timestamp()
                end_score = end_time.timestamp()
                
                data = await self._execute_redis_command(
                    'zrangebyscore', key, start_score, end_score, withscores=True
                )
                
                for item, score in data:
                    try:
                        metric_data = json.loads(item)
                        all_metrics.append(metric_data)
                    except json.JSONDecodeError:
                        continue
            
            # Sort by timestamp and limit
            all_metrics.sort(key=lambda x: x['timestamp'])
            return all_metrics[-limit:] if len(all_metrics) > limit else all_metrics
            
        except Exception as e:
            logger.error(f"Error retrieving database metrics: {e}")
            return []
    
    async def get_system_health(self) -> Dict[str, Any]:
        """Get current system health status"""
        try:
            health_data = {}
            
            # Get latest metrics for each system component
            for metric_type in [MetricType.SYSTEM_CPU, MetricType.SYSTEM_MEMORY, 
                              MetricType.SYSTEM_DISK, MetricType.SYSTEM_NETWORK]:
                health_key = f"{self.HEALTH_KEY}:{metric_type.value}"
                data = await self._execute_redis_command('hgetall', health_key)
                
                if data:
                    try:
                        health_data[metric_type.value] = {
                            'value': float(data.get('latest_value', 0)),
                            'timestamp': data.get('latest_timestamp'),
                            'metadata': json.loads(data.get('metadata', '{}'))
                        }
                    except (ValueError, json.JSONDecodeError):
                        continue
            
            # Add overall status
            cpu_value = health_data.get('system_cpu', {}).get('value', 0)
            memory_value = health_data.get('system_memory', {}).get('value', 0)
            disk_value = health_data.get('system_disk', {}).get('value', 0)
            
            # Determine overall health status and calculate health score
            health_score = 100
            issues = []
            
            if cpu_value > 90:
                status = "critical"
                health_score -= 40
                issues.append(f"Critical CPU usage: {cpu_value:.1f}%")
            elif cpu_value > 75:
                status = "warning"
                health_score -= 20
                issues.append(f"High CPU usage: {cpu_value:.1f}%")
            else:
                status = "healthy"
                
            if memory_value > 90:
                if status != "critical":
                    status = "critical"
                health_score -= 35
                issues.append(f"Critical memory usage: {memory_value:.1f}%")
            elif memory_value > 80:
                if status == "healthy":
                    status = "warning"
                health_score -= 15
                issues.append(f"High memory usage: {memory_value:.1f}%")
                
            if disk_value > 95:
                if status != "critical":
                    status = "critical"
                health_score -= 30
                issues.append(f"Critical disk usage: {disk_value:.1f}%")
            elif disk_value > 85:
                if status == "healthy":
                    status = "warning"
                health_score -= 10
                issues.append(f"High disk usage: {disk_value:.1f}%")
            
            health_score = max(health_score, 0)  # Don't go below 0
            
            # Get recent HTTP metrics for error rate
            recent_http = await self.get_http_metrics(hours_back=1, limit=100)
            error_rate = 0
            recent_requests = len(recent_http)
            avg_response_time = 0
            
            if recent_http:
                error_count = sum(1 for req in recent_http if req.get('status_code', 200) >= 400)
                error_rate = error_count / len(recent_http)
                avg_response_time = sum(req.get('response_time_ms', 0) for req in recent_http) / len(recent_http)
                
                if error_rate > 0.1:
                    if status == "healthy":
                        status = "warning"
                    health_score -= 15
                    issues.append(f"High error rate: {error_rate:.1%}")
            
            # Extract current metrics for frontend compatibility
            cpu_metadata = health_data.get('system_cpu', {}).get('metadata', {})
            memory_metadata = health_data.get('system_memory', {}).get('metadata', {})
            disk_metadata = health_data.get('system_disk', {}).get('metadata', {})
            
            return {
                "status": status,
                "status_color": "#2e7d32" if status == "healthy" else "#f57c00" if status == "warning" else "#d32f2f",
                "health_score": health_score,
                "issues": issues,
                "timestamp": isoformat_now(),
                "current_metrics": {
                    "cpu_percent": cpu_value,
                    "memory_percent": memory_value,
                    "disk_percent": disk_value,
                    "memory_gb": memory_metadata.get('used_gb', 0),
                    "memory_total_gb": memory_metadata.get('total_gb', 0),
                    "disk_gb": disk_metadata.get('used_gb', 0),
                    "disk_total_gb": disk_metadata.get('total_gb', 0)
                },
                "recent_requests": recent_requests,
                "error_rate": error_rate,
                "avg_response_time_ms": avg_response_time,
                "components": health_data,
                "thresholds": {
                    "cpu_warning": 75,
                    "cpu_critical": 90,
                    "memory_warning": 80,
                    "memory_critical": 90,
                    "disk_warning": 85,
                    "disk_critical": 95
                }
            }
            
        except Exception as e:
            logger.error(f"Error retrieving system health: {e}")
            return {
                "status": "unknown", 
                "status_color": "#888888",
                "health_score": 0,
                "issues": [f"Error retrieving health data: {str(e)}"],
                "current_metrics": {
                    "cpu_percent": 0,
                    "memory_percent": 0,
                    "disk_percent": 0,
                    "memory_gb": 0,
                    "memory_total_gb": 0,
                    "disk_gb": 0,
                    "disk_total_gb": 0
                },
                "recent_requests": 0,
                "error_rate": 0,
                "avg_response_time_ms": 0,
                "error": str(e)
            }
    
    async def clear_metrics(self) -> Dict[str, int]:
        """Clear all metrics data"""
        try:
            # Get all metric keys
            patterns = [
                f"{self.TIMESERIES_PREFIX}{self.SYSTEM_METRICS_KEY}:*",
                f"{self.TIMESERIES_PREFIX}{self.HTTP_METRICS_KEY}:*",
                f"{self.TIMESERIES_PREFIX}{self.DB_METRICS_KEY}:*",
                f"{self.HEALTH_KEY}:*",
                f"{self.HTTP_METRICS_KEY}:stats"
            ]
            
            total_deleted = 0
            for pattern in patterns:
                keys = await self._execute_redis_command('keys', pattern)
                if keys:
                    deleted = await self._execute_redis_command('delete', *keys)
                    total_deleted += deleted
            
            return {"deleted_keys": total_deleted}
            
        except Exception as e:
            logger.error(f"Error clearing metrics: {e}")
            return {"error": str(e)}
    
    async def _execute_redis_command(self, command: str, *args, **kwargs):
        """Execute Redis command asynchronously"""
        loop = asyncio.get_event_loop()
        redis_method = getattr(self.redis, command)
        
        # Handle different Redis command patterns
        if kwargs:
            # For commands that need keyword arguments, create a wrapper function
            def redis_call():
                return redis_method(*args, **kwargs)
            return await loop.run_in_executor(self.executor, redis_call)
        else:
            # For simple commands with only positional arguments
            return await loop.run_in_executor(self.executor, redis_method, *args)
    
    async def cleanup_old_metrics(self) -> Dict[str, int]:
        """Clean up old metrics beyond retention period"""
        try:
            cutoff_time = now_local() - timedelta(hours=self.retention_hours)
            cutoff_score = cutoff_time.timestamp()
            
            # Find all time series keys
            all_patterns = [
                f"{self.TIMESERIES_PREFIX}{self.SYSTEM_METRICS_KEY}:*",
                f"{self.TIMESERIES_PREFIX}{self.HTTP_METRICS_KEY}:*", 
                f"{self.TIMESERIES_PREFIX}{self.DB_METRICS_KEY}:*"
            ]
            
            total_cleaned = 0
            for pattern in all_patterns:
                keys = await self._execute_redis_command('keys', pattern)
                for key in keys:
                    # Remove old entries from sorted sets
                    cleaned = await self._execute_redis_command(
                        'zremrangebyscore', key, '-inf', cutoff_score
                    )
                    total_cleaned += cleaned
                    
                    # Remove empty keys
                    count = await self._execute_redis_command('zcard', key)
                    if count == 0:
                        await self._execute_redis_command('delete', key)
            
            return {"cleaned_entries": total_cleaned}
            
        except Exception as e:
            logger.error(f"Error cleaning up old metrics: {e}")
            return {"error": str(e)}


# Global metrics cache instance
metrics_cache: Optional[RedisMetricsCache] = None


def get_metrics_cache() -> RedisMetricsCache:
    """Get global metrics cache instance"""
    global metrics_cache
    if metrics_cache is None:
        from app.core.redis import redis_client
        metrics_cache = RedisMetricsCache(redis_client)
    return metrics_cache 