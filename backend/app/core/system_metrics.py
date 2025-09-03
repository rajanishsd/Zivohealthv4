"""
System Performance Metrics Collector

Collects real-time system metrics including CPU, memory, disk, network,
and database performance for backend monitoring and observability.
Uses Redis-based persistent storage for metrics.
"""

import psutil
import time
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json
from dataclasses import dataclass, asdict
from enum import Enum
import logging
import threading
from app.utils.timezone import isoformat_now

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
class SystemMetric:
    """Individual system metric data point"""
    timestamp: str
    metric_type: MetricType
    value: float
    unit: str
    metadata: Dict[str, Any]
    tags: Dict[str, str]


@dataclass
class HTTPRequestMetric:
    """HTTP request performance metric"""
    timestamp: str
    method: str
    endpoint: str
    status_code: int
    response_time_ms: float
    request_size_bytes: Optional[int] = None
    response_size_bytes: Optional[int] = None
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None


@dataclass
class DatabaseMetric:
    """Database operation performance metric"""
    timestamp: str
    operation_type: str  # SELECT, INSERT, UPDATE, DELETE
    table_name: Optional[str]
    duration_ms: float
    rows_affected: Optional[int] = None
    query_hash: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None


class SystemMetricsCollector:
    """Collects and stores system performance metrics using Redis cache"""
    
    def __init__(self, collection_interval: float = 5.0):
        self.collection_interval = collection_interval
        self._collecting = False
        self._collection_task = None
        self._lock = threading.Lock()
        
        # Baseline measurements for deltas
        self._last_network_io = None
        self._last_disk_io = None
        self._process = psutil.Process()
        
        # Redis cache for persistent storage
        self._cache = None
        
    async def start_collection(self):
        """Start background metrics collection"""
        if self._collecting:
            return
        
        # Initialize Redis cache
        from .metrics_cache import get_metrics_cache
        self._cache = get_metrics_cache()
            
        self._collecting = True
        self._collection_task = asyncio.create_task(self._collect_metrics_loop())
        logger.info("System metrics collection started with Redis persistence")
        
    async def stop_collection(self):
        """Stop background metrics collection"""
        if not self._collecting:
            return
            
        self._collecting = False
        if self._collection_task:
            self._collection_task.cancel()
            try:
                await self._collection_task
            except asyncio.CancelledError:
                pass
        logger.info("System metrics collection stopped")
        
    async def _collect_metrics_loop(self):
        """Background task that collects metrics at regular intervals"""
        try:
            while self._collecting:
                await self._collect_system_metrics()
                await asyncio.sleep(self.collection_interval)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            import traceback
            logger.error(f"Error in metrics collection loop: {e}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            
    async def _collect_system_metrics(self):
        """Collect all system metrics"""
        timestamp = isoformat_now()
        
        try:
            # CPU Metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            
            await self._add_metric(SystemMetric(
                timestamp=timestamp,
                metric_type=MetricType.SYSTEM_CPU,
                value=cpu_percent,
                unit="percent",
                metadata={
                    "cpu_count": cpu_count,
                    "cpu_freq_current": cpu_freq.current if cpu_freq else None,
                    "cpu_freq_max": cpu_freq.max if cpu_freq else None,
                    "load_avg": list(psutil.getloadavg()) if hasattr(psutil, 'getloadavg') else None
                },
                tags={"component": "cpu"}
            ))
            
            # Memory Metrics
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            await self._add_metric(SystemMetric(
                timestamp=timestamp,
                metric_type=MetricType.SYSTEM_MEMORY,
                value=memory.percent,
                unit="percent",
                metadata={
                    "total_gb": round(memory.total / (1024**3), 2),
                    "available_gb": round(memory.available / (1024**3), 2),
                    "used_gb": round(memory.used / (1024**3), 2),
                    "swap_total_gb": round(swap.total / (1024**3), 2),
                    "swap_used_gb": round(swap.used / (1024**3), 2),
                    "swap_percent": swap.percent
                },
                tags={"component": "memory"}
            ))
            
            # Disk Metrics
            disk_usage = psutil.disk_usage('/')
            disk_io = psutil.disk_io_counters()
            
            disk_read_rate = 0
            disk_write_rate = 0
            
            if self._last_disk_io and disk_io:
                time_delta = self.collection_interval
                disk_read_rate = (disk_io.read_bytes - self._last_disk_io.read_bytes) / time_delta
                disk_write_rate = (disk_io.write_bytes - self._last_disk_io.write_bytes) / time_delta
            
            self._last_disk_io = disk_io
            
            await self._add_metric(SystemMetric(
                timestamp=timestamp,
                metric_type=MetricType.SYSTEM_DISK,
                value=disk_usage.percent,
                unit="percent",
                metadata={
                    "total_gb": round(disk_usage.total / (1024**3), 2),
                    "used_gb": round(disk_usage.used / (1024**3), 2),
                    "free_gb": round(disk_usage.free / (1024**3), 2),
                    "read_rate_mbps": round(disk_read_rate / (1024**2), 2),
                    "write_rate_mbps": round(disk_write_rate / (1024**2), 2),
                    "read_count": disk_io.read_count if disk_io else 0,
                    "write_count": disk_io.write_count if disk_io else 0
                },
                tags={"component": "disk"}
            ))
            
            # Network Metrics
            network_io = psutil.net_io_counters()
            try:
                network_connections = len(psutil.net_connections())
            except (psutil.AccessDenied, PermissionError):
                # Fallback to 0 if we don't have permission to access network connections
                network_connections = 0
            
            network_recv_rate = 0
            network_sent_rate = 0
            
            if self._last_network_io and network_io:
                time_delta = self.collection_interval
                network_recv_rate = (network_io.bytes_recv - self._last_network_io.bytes_recv) / time_delta
                network_sent_rate = (network_io.bytes_sent - self._last_network_io.bytes_sent) / time_delta
            
            self._last_network_io = network_io
            
            await self._add_metric(SystemMetric(
                timestamp=timestamp,
                metric_type=MetricType.SYSTEM_NETWORK,
                value=network_connections,
                unit="connections",
                metadata={
                    "recv_rate_mbps": round(network_recv_rate / (1024**2), 2),
                    "sent_rate_mbps": round(network_sent_rate / (1024**2), 2),
                    "packets_sent": network_io.packets_sent if network_io else 0,
                    "packets_recv": network_io.packets_recv if network_io else 0,
                    "errors_in": network_io.errin if network_io else 0,
                    "errors_out": network_io.errout if network_io else 0,
                    "drops_in": network_io.dropin if network_io else 0,
                    "drops_out": network_io.dropout if network_io else 0
                },
                tags={"component": "network"}
            ))
            
            # Process-specific metrics
            try:
                process_cpu = self._process.cpu_percent()
                process_memory = self._process.memory_info()
                
                # Try to get connections and open files, fall back safely if unsupported/denied
                try:
                    if hasattr(self._process, "connections"):
                        # Use supported API for process connections
                        process_connections = len(self._process.connections(kind="inet"))
                    else:
                        # Fallback to system-level connections if per-process not available
                        process_connections = len(psutil.net_connections(kind="inet"))
                except (psutil.AccessDenied, PermissionError, AttributeError):
                    process_connections = 0
                    
                try:
                    process_open_files = len(self._process.open_files())
                except (psutil.AccessDenied, PermissionError):
                    process_open_files = 0
                
                await self._add_metric(SystemMetric(
                    timestamp=timestamp,
                    metric_type=MetricType.HTTP_REQUEST,  # Using as proxy for process metrics
                    value=process_cpu,
                    unit="percent",
                    metadata={
                        "process_memory_mb": round(process_memory.rss / (1024**2), 2),
                        "process_threads": self._process.num_threads(),
                        "process_connections": process_connections,
                        "process_open_files": process_open_files
                    },
                    tags={"component": "process", "type": "application"}
                ))
            except (psutil.AccessDenied, PermissionError, psutil.NoSuchProcess) as e:
                # Log and skip process-specific metrics if we can't access them
                logger.warning(f"Cannot access process metrics (likely permission issue): {e}")
            
        except Exception as e:
            import traceback
            logger.error(f"Error collecting system metrics: {e}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            
    async def _add_metric(self, metric: SystemMetric):
        """Add metric to Redis storage"""
        if self._cache:
            from .metrics_cache import BaseMetric
            base_metric = BaseMetric(
                timestamp=metric.timestamp,
                metric_type=metric.metric_type.value,
                value=metric.value,
                metadata={**metric.metadata, "unit": metric.unit, "tags": metric.tags}
            )
            await self._cache.store_system_metric(base_metric)
            
    def record_http_request(self, method: str, endpoint: str, status_code: int, 
                          response_time_ms: float, request_size: Optional[int] = None,
                          response_size: Optional[int] = None, user_agent: Optional[str] = None,
                          ip_address: Optional[str] = None):
        """Record HTTP request metrics"""
        if self._cache:
            # Use asyncio to run the async method
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If we're in an async context, schedule the task
                    asyncio.create_task(self._cache.store_http_metric(
                        method=method,
                        endpoint=endpoint,
                        status_code=status_code,
                        response_time_ms=response_time_ms,
                        request_size_bytes=request_size,
                        response_size_bytes=response_size,
                        user_agent=user_agent,
                        ip_address=ip_address
                    ))
                else:
                    # If not in async context, run synchronously
                    loop.run_until_complete(self._cache.store_http_metric(
                        method=method,
                        endpoint=endpoint,
                        status_code=status_code,
                        response_time_ms=response_time_ms,
                        request_size_bytes=request_size,
                        response_size_bytes=response_size,
                        user_agent=user_agent,
                        ip_address=ip_address
                    ))
            except Exception as e:
                logger.error(f"Error recording HTTP metric: {e}")
            
    def record_database_operation(self, operation_type: str, duration_ms: float,
                                table_name: Optional[str] = None, rows_affected: Optional[int] = None,
                                query_hash: Optional[str] = None, success: bool = True,
                                error_message: Optional[str] = None):
        """Record database operation metrics"""
        if self._cache:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self._cache.store_database_metric(
                        operation_type=operation_type,
                        duration_ms=duration_ms,
                        table_name=table_name,
                        rows_affected=rows_affected,
                        query_hash=query_hash,
                        success=success,
                        error_message=error_message
                    ))
                else:
                    loop.run_until_complete(self._cache.store_database_metric(
                        operation_type=operation_type,
                        duration_ms=duration_ms,
                        table_name=table_name,
                        rows_affected=rows_affected,
                        query_hash=query_hash,
                        success=success,
                        error_message=error_message
                    ))
            except Exception as e:
                logger.error(f"Error recording database metric: {e}")
            
    async def get_metrics(self, metric_type: Optional[MetricType] = None, 
                   hours_back: int = 24, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get system metrics with optional filtering"""
        if self._cache:
            metric_type_str = metric_type.value if metric_type else None
            return await self._cache.get_system_metrics(
                metric_type=metric_type_str,
                hours_back=hours_back,
                limit=limit
            )
        return []
            
    async def get_http_metrics(self, hours_back: int = 24, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get HTTP request metrics"""
        if self._cache:
            return await self._cache.get_http_metrics(
                hours_back=hours_back,
                limit=limit
            )
        return []
            
    async def get_database_metrics(self, hours_back: int = 24, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get database operation metrics"""
        if self._cache:
            return await self._cache.get_database_metrics(
                hours_back=hours_back,
                limit=limit
            )
        return []
            
    async def get_system_health(self) -> Dict[str, Any]:
        """Get current system health status"""
        try:
            if self._cache:
                return await self._cache.get_system_health()
            
            # Fallback to direct system metrics if cache not available
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Recent HTTP metrics (last hour)
            recent_http = await self.get_http_metrics(hours_back=1)
            
            # Calculate health status
            health_issues = []
            health_score = 100
            
            if cpu_percent > 80:
                health_issues.append(f"High CPU usage: {cpu_percent:.1f}%")
                health_score -= 30
            elif cpu_percent > 60:
                health_score -= 15
                
            if memory.percent > 85:
                health_issues.append(f"High memory usage: {memory.percent:.1f}%")
                health_score -= 25
            elif memory.percent > 70:
                health_score -= 10
                
            if disk.percent > 90:
                health_issues.append(f"High disk usage: {disk.percent:.1f}%")
                health_score -= 20
            elif disk.percent > 80:
                health_score -= 10
                
            # HTTP error rate
            if recent_http:
                error_count = sum(1 for req in recent_http if req['status_code'] >= 400)
                error_rate = error_count / len(recent_http)
                if error_rate > 0.1:
                    health_issues.append(f"High error rate: {error_rate:.1%}")
                    health_score -= 20
                    
                # Average response time
                avg_response_time = sum(req['response_time_ms'] for req in recent_http) / len(recent_http)
                if avg_response_time > 2000:
                    health_issues.append(f"Slow response times: {avg_response_time:.0f}ms")
                    health_score -= 15
                    
            # Determine overall status
            if health_score >= 90:
                status = "healthy"
                status_color = "green"
            elif health_score >= 70:
                status = "degraded"
                status_color = "orange"
            else:
                status = "unhealthy"
                status_color = "red"
                
            return {
                "status": status,
                "status_color": status_color,
                "health_score": max(0, health_score),
                "issues": health_issues,
                "current_metrics": {
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "disk_percent": disk.percent,
                    "memory_gb": round(memory.used / (1024**3), 2),
                    "memory_total_gb": round(memory.total / (1024**3), 2),
                    "disk_gb": round(disk.used / (1024**3), 2),
                    "disk_total_gb": round(disk.total / (1024**3), 2)
                },
                "recent_requests": len(recent_http),
                "error_rate": error_count / len(recent_http) if recent_http else 0,
                "avg_response_time_ms": sum(req['response_time_ms'] for req in recent_http) / len(recent_http) if recent_http else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting system health: {e}")
            return {
                "status": "unknown",
                "status_color": "gray",
                "health_score": 0,
                "issues": [f"Error retrieving health data: {str(e)}"],
                "current_metrics": {},
                "recent_requests": 0,
                "error_rate": 0,
                "avg_response_time_ms": 0
            }


# Global instance
system_metrics = SystemMetricsCollector() 