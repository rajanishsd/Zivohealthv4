"""
Audit Trail API Endpoints

Provides API access to agent interaction logs for compliance and debugging.
Essential for medical applications requiring audit trails.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from app.core.agent_logger import agent_logger
from app.api.dependencies import get_current_user
from app.models.user import User
from app.utils.timezone import now_local

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/request/{request_id}")
async def get_request_lineage(
    request_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get complete lineage for a specific request"""
    
    lineage = agent_logger.get_request_lineage(request_id)
    
    if not lineage:
        raise HTTPException(status_code=404, detail="Request not found")
    
    return {
        "request_id": request_id,
        "total_events": len(lineage),
        "lineage": lineage,
        "summary": {
            "agents_involved": list(set(event["agent_name"] for event in lineage)),
            "tools_used": list(set(event.get("tool_used") for event in lineage if event.get("tool_used"))),
            "errors": [event for event in lineage if event["log_level"] == "ERROR"],
            "start_time": lineage[0]["timestamp"] if lineage else None,
            "end_time": lineage[-1]["timestamp"] if lineage else None
        }
    }


@router.get("/requests")
async def get_recent_requests(
    limit: int = Query(50, ge=1, le=1000),
    user_id: Optional[int] = Query(None),
    agent_name: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get recent requests with filtering options"""
    
    # Filter logs based on criteria
    filtered_logs = agent_logger.interaction_log.copy()
    
    if user_id:
        filtered_logs = [log for log in filtered_logs if log.user_id == user_id]
    
    if agent_name:
        filtered_logs = [log for log in filtered_logs if log.agent_name == agent_name]
    
    if event_type:
        filtered_logs = [log for log in filtered_logs if log.event_type.value == event_type]
    
    if start_date:
        filtered_logs = [log for log in filtered_logs if datetime.fromisoformat(log.timestamp) >= start_date]
    
    if end_date:
        filtered_logs = [log for log in filtered_logs if datetime.fromisoformat(log.timestamp) <= end_date]
    
    # Group by request_id to get unique requests
    request_groups = {}
    for log in filtered_logs:
        if log.request_id not in request_groups:
            request_groups[log.request_id] = []
        request_groups[log.request_id].append(log)
    
    # Sort by most recent and limit
    sorted_requests = sorted(
        request_groups.values(),
        key=lambda group: group[0].timestamp,
        reverse=True
    )[:limit]
    
    return {
        "total_requests": len(sorted_requests),
        "filters_applied": {
            "user_id": user_id,
            "agent_name": agent_name,
            "event_type": event_type,
            "start_date": start_date,
            "end_date": end_date
        },
        "requests": [
            {
                "request_id": group[0].request_id,
                "user_id": group[0].user_id,
                "start_time": group[0].timestamp,
                "end_time": group[-1].timestamp,
                "total_events": len(group),
                "agents_involved": list(set(log.agent_name for log in group)),
                "has_errors": any(log.log_level.value == "ERROR" for log in group),
                "first_message": group[0].details.get("user_message", "")[:100] + "..." if len(group[0].details.get("user_message", "")) > 100 else group[0].details.get("user_message", "")
            }
            for group in sorted_requests
        ]
    }


@router.get("/agents/performance")
async def get_agent_performance(
    hours: int = Query(24, ge=1, le=168),  # Last 24 hours by default, max 1 week
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get performance metrics for all agents"""
    
    cutoff_time = now_local() - timedelta(hours=hours)
    recent_logs = [
        log for log in agent_logger.interaction_log
        if datetime.fromisoformat(log.timestamp) >= cutoff_time
    ]
    
    agent_stats = {}
    
    for log in recent_logs:
        agent_name = log.agent_name
        if agent_name not in agent_stats:
            agent_stats[agent_name] = {
                "total_interactions": 0,
                "errors": 0,
                "total_execution_time_ms": 0,
                "tool_usage": {},
                "event_types": {}
            }
        
        stats = agent_stats[agent_name]
        stats["total_interactions"] += 1
        
        if log.log_level.value == "ERROR":
            stats["errors"] += 1
        
        if log.execution_time_ms:
            stats["total_execution_time_ms"] += log.execution_time_ms
        
        if log.tool_used:
            stats["tool_usage"][log.tool_used] = stats["tool_usage"].get(log.tool_used, 0) + 1
        
        event_type = log.event_type.value
        stats["event_types"][event_type] = stats["event_types"].get(event_type, 0) + 1
    
    # Calculate additional metrics
    for agent_name, stats in agent_stats.items():
        if stats["total_interactions"] > 0:
            stats["error_rate"] = stats["errors"] / stats["total_interactions"]
            stats["avg_execution_time_ms"] = stats["total_execution_time_ms"] / stats["total_interactions"]
        else:
            stats["error_rate"] = 0
            stats["avg_execution_time_ms"] = 0
    
    return {
        "time_period_hours": hours,
        "total_agents": len(agent_stats),
        "agents": agent_stats
    }


@router.get("/tools/usage")
async def get_tool_usage_stats(
    hours: int = Query(24, ge=1, le=168),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get tool usage statistics"""
    
    cutoff_time = now_local() - timedelta(hours=hours)
    tool_logs = [
        log for log in agent_logger.interaction_log
        if (datetime.fromisoformat(log.timestamp) >= cutoff_time and 
            log.event_type.value == "TOOL_EXECUTION" and 
            log.tool_used)
    ]
    
    tool_stats = {}
    
    for log in tool_logs:
        tool_name = log.tool_used
        if tool_name not in tool_stats:
            tool_stats[tool_name] = {
                "usage_count": 0,
                "total_execution_time_ms": 0,
                "errors": 0,
                "agents_using": set()
            }
        
        stats = tool_stats[tool_name]
        stats["usage_count"] += 1
        stats["agents_using"].add(log.agent_name)
        
        if log.execution_time_ms:
            stats["total_execution_time_ms"] += log.execution_time_ms
        
        if "error" in log.details.get("result_preview", "").lower():
            stats["errors"] += 1
    
    # Convert sets to lists and calculate averages
    for tool_name, stats in tool_stats.items():
        stats["agents_using"] = list(stats["agents_using"])
        if stats["usage_count"] > 0:
            stats["avg_execution_time_ms"] = stats["total_execution_time_ms"] / stats["usage_count"]
            stats["error_rate"] = stats["errors"] / stats["usage_count"]
        else:
            stats["avg_execution_time_ms"] = 0
            stats["error_rate"] = 0
    
    return {
        "time_period_hours": hours,
        "total_tools": len(tool_stats),
        "tools": tool_stats
    }


@router.get("/errors")
async def get_error_summary(
    hours: int = Query(24, ge=1, le=168),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get error summary and patterns"""
    
    cutoff_time = now_local() - timedelta(hours=hours)
    error_logs = [
        log for log in agent_logger.interaction_log
        if (datetime.fromisoformat(log.timestamp) >= cutoff_time and 
            log.log_level.value == "ERROR")
    ]
    
    error_summary = {
        "total_errors": len(error_logs),
        "errors_by_agent": {},
        "errors_by_type": {},
        "recent_errors": []
    }
    
    for log in error_logs:
        # Count by agent
        agent_name = log.agent_name
        error_summary["errors_by_agent"][agent_name] = error_summary["errors_by_agent"].get(agent_name, 0) + 1
        
        # Count by error type
        error_type = log.error_details.get("error_type", "Unknown") if log.error_details else "Unknown"
        error_summary["errors_by_type"][error_type] = error_summary["errors_by_type"].get(error_type, 0) + 1
        
        # Add to recent errors
        error_summary["recent_errors"].append({
            "timestamp": log.timestamp,
            "agent_name": log.agent_name,
            "error_type": error_type,
            "error_message": log.error_details.get("error_message", log.message) if log.error_details else log.message,
            "request_id": log.request_id
        })
    
    # Sort recent errors by timestamp (most recent first)
    error_summary["recent_errors"] = sorted(
        error_summary["recent_errors"][-50:],  # Last 50 errors
        key=lambda x: x["timestamp"],
        reverse=True
    )
    
    return error_summary


@router.get("/health")
async def get_system_health(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get overall system health metrics"""
    
    last_hour = now_local() - timedelta(hours=1)
    recent_logs = [
        log for log in agent_logger.interaction_log
        if datetime.fromisoformat(log.timestamp) >= last_hour
    ]
    
    total_requests = len(set(log.request_id for log in recent_logs))
    total_errors = len([log for log in recent_logs if log.log_level.value == "ERROR"])
    
    health_status = "healthy"
    if total_requests > 0:
        error_rate = total_errors / total_requests
        if error_rate > 0.1:  # More than 10% error rate
            health_status = "degraded"
        if error_rate > 0.3:  # More than 30% error rate
            health_status = "unhealthy"
    
    return {
        "status": health_status,
        "last_hour_metrics": {
            "total_requests": total_requests,
            "total_errors": total_errors,
            "error_rate": total_errors / total_requests if total_requests > 0 else 0,
            "agents_active": len(set(log.agent_name for log in recent_logs)),
            "avg_response_time_ms": sum(log.execution_time_ms for log in recent_logs if log.execution_time_ms) / len([log for log in recent_logs if log.execution_time_ms]) if [log for log in recent_logs if log.execution_time_ms] else 0
        },
        "total_logs_in_memory": len(agent_logger.interaction_log)
    } 