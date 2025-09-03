"""
Performance Monitoring API Routes

Endpoints for retrieving system performance metrics, HTTP request metrics,
database performance data, and overall system health status.
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from ..core.system_metrics import system_metrics, MetricType
from ..core.database_metrics import db_monitor
from app.utils.timezone import isoformat_now

router = APIRouter(prefix="/performance", tags=["Performance Monitoring"])


@router.get("/system/health")
async def get_system_health() -> Dict[str, Any]:
    """Get current system health status and key metrics"""
    try:
        return await system_metrics.get_system_health()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving system health: {str(e)}")


@router.get("/system/metrics")
async def get_system_metrics(
    metric_type: Optional[str] = Query(None, description="Filter by metric type (cpu, memory, disk, network)"),
    hours: int = Query(24, ge=1, le=168, description="Hours of data to retrieve"),
    limit: int = Query(1000, ge=1, le=5000, description="Maximum number of data points")
) -> Dict[str, Any]:
    """Get system performance metrics"""
    try:
        # Convert string to MetricType enum if provided
        filter_type = None
        if metric_type:
            type_mapping = {
                "cpu": MetricType.SYSTEM_CPU,
                "memory": MetricType.SYSTEM_MEMORY,
                "disk": MetricType.SYSTEM_DISK,
                "network": MetricType.SYSTEM_NETWORK
            }
            filter_type = type_mapping.get(metric_type.lower())
            if not filter_type:
                raise HTTPException(status_code=400, detail=f"Invalid metric type: {metric_type}")
        
        metrics = await system_metrics.get_metrics(
            metric_type=filter_type,
            hours_back=hours,
            limit=limit
        )
        
        return {
            "metric_type": metric_type,
            "hours": hours,
            "total_points": len(metrics),
            "metrics": metrics
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving system metrics: {str(e)}")


@router.get("/system/overview")
async def get_system_overview(
    hours: int = Query(24, ge=1, le=168, description="Hours of data for calculations")
) -> Dict[str, Any]:
    """Get system performance overview with aggregated metrics"""
    try:
        # Get current system health
        health = await system_metrics.get_system_health()
        
        # Get metrics for the specified time period
        all_metrics = await system_metrics.get_metrics(hours_back=hours)
        
        # Group metrics by type for analysis
        cpu_metrics = [m for m in all_metrics if m['metric_type'] == MetricType.SYSTEM_CPU.value]
        memory_metrics = [m for m in all_metrics if m['metric_type'] == MetricType.SYSTEM_MEMORY.value]
        disk_metrics = [m for m in all_metrics if m['metric_type'] == MetricType.SYSTEM_DISK.value]
        network_metrics = [m for m in all_metrics if m['metric_type'] == MetricType.SYSTEM_NETWORK.value]
        
        # Calculate aggregated statistics
        def calculate_stats(metrics_list, value_key='value'):
            if not metrics_list:
                return {"avg": 0, "min": 0, "max": 0, "current": 0}
            
            values = [m[value_key] for m in metrics_list]
            return {
                "avg": round(sum(values) / len(values), 2),
                "min": round(min(values), 2),
                "max": round(max(values), 2),
                "current": round(values[-1], 2) if values else 0
            }
        
        return {
            "time_period_hours": hours,
            "system_health": health,
            "overview": {
                "cpu": calculate_stats(cpu_metrics),
                "memory": calculate_stats(memory_metrics),
                "disk": calculate_stats(disk_metrics),
                "network_connections": calculate_stats(network_metrics)
            },
            "detailed_stats": {
                "cpu_load_avg": cpu_metrics[-1]['metadata'].get('load_avg') if cpu_metrics else None,
                "memory_details": {
                    "total_gb": memory_metrics[-1]['metadata'].get('total_gb') if memory_metrics else 0,
                    "available_gb": memory_metrics[-1]['metadata'].get('available_gb') if memory_metrics else 0,
                    "swap_percent": memory_metrics[-1]['metadata'].get('swap_percent') if memory_metrics else 0
                },
                "disk_details": {
                    "total_gb": disk_metrics[-1]['metadata'].get('total_gb') if disk_metrics else 0,
                    "free_gb": disk_metrics[-1]['metadata'].get('free_gb') if disk_metrics else 0,
                    "read_rate_mbps": disk_metrics[-1]['metadata'].get('read_rate_mbps') if disk_metrics else 0,
                    "write_rate_mbps": disk_metrics[-1]['metadata'].get('write_rate_mbps') if disk_metrics else 0
                },
                "network_details": {
                    "recv_rate_mbps": network_metrics[-1]['metadata'].get('recv_rate_mbps') if network_metrics else 0,
                    "sent_rate_mbps": network_metrics[-1]['metadata'].get('sent_rate_mbps') if network_metrics else 0,
                    "errors_in": network_metrics[-1]['metadata'].get('errors_in') if network_metrics else 0,
                    "errors_out": network_metrics[-1]['metadata'].get('errors_out') if network_metrics else 0
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving system overview: {str(e)}")


@router.get("/http/metrics")
async def get_http_metrics(
    hours: int = Query(24, ge=1, le=168, description="Hours of data to retrieve"),
    limit: int = Query(1000, ge=1, le=5000, description="Maximum number of requests")
) -> Dict[str, Any]:
    """Get HTTP request performance metrics"""
    try:
        metrics = await system_metrics.get_http_metrics(hours_back=hours, limit=limit)
        
        return {
            "hours": hours,
            "total_requests": len(metrics),
            "requests": metrics
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving HTTP metrics: {str(e)}")


@router.get("/http/overview")
async def get_http_overview(
    hours: int = Query(24, ge=1, le=168, description="Hours of data for analysis")
) -> Dict[str, Any]:
    """Get HTTP performance overview with aggregated statistics"""
    try:
        metrics = await system_metrics.get_http_metrics(hours_back=hours)
        
        if not metrics:
            return {
                "hours": hours,
                "total_requests": 0,
                "overview": {},
                "endpoint_stats": [],
                "status_distribution": {},
                "performance_stats": {}
            }
        
        # Calculate overall statistics
        total_requests = len(metrics)
        response_times = [m['response_time_ms'] for m in metrics]
        status_codes = [m['status_code'] for m in metrics]
        
        # Error rate calculation
        error_count = sum(1 for code in status_codes if code >= 400)
        error_rate = error_count / total_requests if total_requests > 0 else 0
        
        # Response time statistics
        avg_response_time = sum(response_times) / len(response_times)
        p95_response_time = sorted(response_times)[int(len(response_times) * 0.95)] if response_times else 0
        p99_response_time = sorted(response_times)[int(len(response_times) * 0.99)] if response_times else 0
        
        # Endpoint statistics
        endpoint_stats = {}
        for metric in metrics:
            endpoint = metric['endpoint']
            if endpoint not in endpoint_stats:
                endpoint_stats[endpoint] = {
                    "count": 0,
                    "total_time": 0,
                    "errors": 0,
                    "methods": set()
                }
            
            stats = endpoint_stats[endpoint]
            stats["count"] += 1
            stats["total_time"] += metric['response_time_ms']
            stats["methods"].add(metric['method'])
            
            if metric['status_code'] >= 400:
                stats["errors"] += 1
        
        # Convert to list with calculated averages
        endpoint_list = []
        for endpoint, stats in endpoint_stats.items():
            endpoint_list.append({
                "endpoint": endpoint,
                "request_count": stats["count"],
                "avg_response_time_ms": round(stats["total_time"] / stats["count"], 2),
                "error_rate": stats["errors"] / stats["count"],
                "methods": list(stats["methods"])
            })
        
        # Sort by request count
        endpoint_list.sort(key=lambda x: x["request_count"], reverse=True)
        
        # Status code distribution
        status_distribution = {}
        for code in status_codes:
            status_range = f"{code // 100}xx"
            status_distribution[status_range] = status_distribution.get(status_range, 0) + 1
        
        return {
            "hours": hours,
            "total_requests": total_requests,
            "overview": {
                "requests_per_hour": round(total_requests / hours, 2),
                "avg_response_time_ms": round(avg_response_time, 2),
                "p95_response_time_ms": round(p95_response_time, 2),
                "p99_response_time_ms": round(p99_response_time, 2),
                "error_rate": round(error_rate, 4),
                "error_count": error_count
            },
            "endpoint_stats": endpoint_list[:20],  # Top 20 endpoints
            "status_distribution": status_distribution,
            "performance_buckets": {
                "fast_requests": sum(1 for t in response_times if t < 100),
                "medium_requests": sum(1 for t in response_times if 100 <= t < 500),
                "slow_requests": sum(1 for t in response_times if 500 <= t < 2000),
                "very_slow_requests": sum(1 for t in response_times if t >= 2000)
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving HTTP overview: {str(e)}")


@router.get("/database/metrics")
async def get_database_metrics(
    hours: int = Query(24, ge=1, le=168, description="Hours of data to retrieve"),
    limit: int = Query(1000, ge=1, le=5000, description="Maximum number of operations")
) -> Dict[str, Any]:
    """Get database operation performance metrics"""
    try:
        metrics = await system_metrics.get_database_metrics(hours_back=hours, limit=limit)
        
        return {
            "hours": hours,
            "total_operations": len(metrics),
            "operations": metrics
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving database metrics: {str(e)}")


@router.get("/database/overview")
async def get_database_overview(
    hours: int = Query(24, ge=1, le=168, description="Hours of data for analysis")
) -> Dict[str, Any]:
    """Get database performance overview with aggregated statistics"""
    try:
        metrics = await system_metrics.get_database_metrics(hours_back=hours)
        
        if not metrics:
            return {
                "hours": hours,
                "total_operations": 0,
                "overview": {},
                "operation_stats": [],
                "table_stats": [],
                "slow_queries": []
            }
        
        # Calculate overall statistics
        total_operations = len(metrics)
        durations = [m['duration_ms'] for m in metrics]
        success_count = sum(1 for m in metrics if m['success'])
        error_count = total_operations - success_count
        
        avg_duration = sum(durations) / len(durations) if durations else 0
        p95_duration = sorted(durations)[int(len(durations) * 0.95)] if durations else 0
        p99_duration = sorted(durations)[int(len(durations) * 0.99)] if durations else 0
        
        # Operation type statistics
        operation_stats = {}
        for metric in metrics:
            op_type = metric['operation_type']
            if op_type not in operation_stats:
                operation_stats[op_type] = {
                    "count": 0,
                    "total_duration": 0,
                    "errors": 0
                }
            
            stats = operation_stats[op_type]
            stats["count"] += 1
            stats["total_duration"] += metric['duration_ms']
            
            if not metric['success']:
                stats["errors"] += 1
        
        operation_list = []
        for op_type, stats in operation_stats.items():
            operation_list.append({
                "operation_type": op_type,
                "count": stats["count"],
                "avg_duration_ms": round(stats["total_duration"] / stats["count"], 2),
                "error_rate": stats["errors"] / stats["count"]
            })
        
        # Table statistics
        table_stats = {}
        for metric in metrics:
            table = metric.get('table_name')
            if table:
                if table not in table_stats:
                    table_stats[table] = {
                        "count": 0,
                        "total_duration": 0,
                        "errors": 0
                    }
                
                stats = table_stats[table]
                stats["count"] += 1
                stats["total_duration"] += metric['duration_ms']
                
                if not metric['success']:
                    stats["errors"] += 1
        
        table_list = []
        for table, stats in table_stats.items():
            table_list.append({
                "table_name": table,
                "operation_count": stats["count"],
                "avg_duration_ms": round(stats["total_duration"] / stats["count"], 2),
                "error_rate": stats["errors"] / stats["count"]
            })
        
        # Sort by operation count
        table_list.sort(key=lambda x: x["operation_count"], reverse=True)
        
        # Slow queries (top 10 slowest)
        slow_queries = sorted(metrics, key=lambda x: x['duration_ms'], reverse=True)[:10]
        
        return {
            "hours": hours,
            "total_operations": total_operations,
            "overview": {
                "operations_per_hour": round(total_operations / hours, 2),
                "avg_duration_ms": round(avg_duration, 2),
                "p95_duration_ms": round(p95_duration, 2),
                "p99_duration_ms": round(p99_duration, 2),
                "success_rate": round(success_count / total_operations, 4),
                "error_count": error_count
            },
            "operation_stats": operation_list,
            "table_stats": table_list[:20],  # Top 20 tables
            "slow_queries": slow_queries,
            "performance_buckets": {
                "fast_queries": sum(1 for d in durations if d < 10),
                "medium_queries": sum(1 for d in durations if 10 <= d < 100),
                "slow_queries": sum(1 for d in durations if 100 <= d < 1000),
                "very_slow_queries": sum(1 for d in durations if d >= 1000)
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving database overview: {str(e)}")


@router.get("/alerts")
async def get_performance_alerts(
    hours: int = Query(24, ge=1, le=168, description="Hours to check for alerts")
) -> Dict[str, Any]:
    """Get performance alerts and warnings"""
    try:
        alerts = []
        warnings = []
        
        # System health check
        health = await system_metrics.get_system_health()
        
        if health["status"] == "unhealthy":
            alerts.extend([{
                "type": "system_health",
                "severity": "critical",
                "message": f"System health is {health['status']}",
                "details": health["issues"]
            }])
        elif health["status"] == "degraded":
            warnings.append({
                "type": "system_health",
                "severity": "warning", 
                "message": f"System performance is {health['status']}",
                "details": health["issues"]
            })
        
        # HTTP performance alerts
        http_metrics = await system_metrics.get_http_metrics(hours_back=1)  # Last hour
        if http_metrics:
            error_rate = sum(1 for m in http_metrics if m['status_code'] >= 400) / len(http_metrics)
            avg_response_time = sum(m['response_time_ms'] for m in http_metrics) / len(http_metrics)
            
            if error_rate > 0.1:  # More than 10% error rate
                alerts.append({
                    "type": "http_errors",
                    "severity": "critical",
                    "message": f"High HTTP error rate: {error_rate:.1%}",
                    "value": error_rate
                })
            elif error_rate > 0.05:  # More than 5% error rate
                warnings.append({
                    "type": "http_errors",
                    "severity": "warning",
                    "message": f"Elevated HTTP error rate: {error_rate:.1%}",
                    "value": error_rate
                })
            
            if avg_response_time > 3000:  # Average response time over 3 seconds
                alerts.append({
                    "type": "response_time",
                    "severity": "critical",
                    "message": f"High average response time: {avg_response_time:.0f}ms",
                    "value": avg_response_time
                })
            elif avg_response_time > 1000:  # Average response time over 1 second
                warnings.append({
                    "type": "response_time",
                    "severity": "warning",
                    "message": f"Elevated response time: {avg_response_time:.0f}ms",
                    "value": avg_response_time
                })
        
        # Database performance alerts
        db_metrics = await system_metrics.get_database_metrics(hours_back=1)  # Last hour
        if db_metrics:
            error_rate = sum(1 for m in db_metrics if not m['success']) / len(db_metrics)
            avg_duration = sum(m['duration_ms'] for m in db_metrics) / len(db_metrics)
            
            if error_rate > 0.05:  # More than 5% error rate
                alerts.append({
                    "type": "database_errors",
                    "severity": "critical",
                    "message": f"High database error rate: {error_rate:.1%}",
                    "value": error_rate
                })
            elif error_rate > 0.01:  # More than 1% error rate
                warnings.append({
                    "type": "database_errors",
                    "severity": "warning",
                    "message": f"Elevated database error rate: {error_rate:.1%}",
                    "value": error_rate
                })
            
            if avg_duration > 1000:  # Average query time over 1 second
                alerts.append({
                    "type": "database_performance",
                    "severity": "critical",
                    "message": f"High database query time: {avg_duration:.0f}ms",
                    "value": avg_duration
                })
            elif avg_duration > 500:  # Average query time over 500ms
                warnings.append({
                    "type": "database_performance",
                    "severity": "warning",
                    "message": f"Elevated database query time: {avg_duration:.0f}ms",
                    "value": avg_duration
                })
        
        return {
            "timestamp": isoformat_now(),
            "hours_checked": hours,
            "alert_count": len(alerts),
            "warning_count": len(warnings),
            "alerts": alerts,
            "warnings": warnings,
            "overall_status": "critical" if alerts else ("warning" if warnings else "ok")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving performance alerts: {str(e)}")


@router.post("/metrics/clear")
async def clear_metrics() -> Dict[str, str]:
    """Clear all stored metrics (useful for testing)"""
    try:
        if system_metrics._cache:
            result = await system_metrics._cache.clear_metrics()
            return {"message": "All metrics cleared successfully", "details": result}
        else:
            return {"message": "No cache available to clear"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing metrics: {str(e)}") 