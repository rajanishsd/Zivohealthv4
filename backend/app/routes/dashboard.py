"""
Dashboard API Endpoints for React Admin

Provides comprehensive data for charts, workflow visualization,
and real-time monitoring in the React Admin dashboard.
Powered by Redis-based telemetry system.
"""

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json
import asyncio
from app.core.redis import redis_client
from app.core.system_metrics import system_metrics

router = APIRouter(tags=["dashboard"])

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                self.active_connections.remove(connection)

manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time dashboard updates"""
    await manager.connect(websocket)
    try:
        while True:
            await asyncio.sleep(10)
            data = {
                "timestamp": datetime.now().isoformat(),
                "metrics": get_real_time_metrics(),
                "recent_requests": get_recent_activity(limit=5)
            }
            await websocket.send_text(json.dumps(data))
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@router.get("/metrics/overview")
async def get_overview_metrics(hours: int = Query(24, ge=1, le=168)) -> Dict[str, Any]:
    """Get overview metrics for dashboard cards using Redis telemetry"""
    
    # Get all recent spans from Redis
    recent_spans = redis_client.zrange('telemetry:recent_spans', 0, -1)
    
    if not recent_spans:
        return {
            "total_requests": 0,
            "total_interactions": 0,
            "error_rate": 0,
            "avg_response_time": 0,
            "active_agents": 0,
            "tools_used": 0,
            "period_hours": hours
        }
    
    # Analyze spans for metrics
    cutoff_time = datetime.now() - timedelta(hours=hours)
    valid_spans = []
    sessions = set()
    agents = set()
    tools = set()
    errors = 0
    durations = []
    
    for span_id in recent_spans:
        span_data = redis_client.get(f'telemetry:span:{span_id}')
        if not span_data:
            continue
            
        span = json.loads(span_data)
        span_time = datetime.fromtimestamp(span['start_time'])
        
        if span_time >= cutoff_time:
            valid_spans.append(span)
            
            # Track sessions (requests)
            user_id = span.get('user_id')
            session_id = span.get('session_id')
            if user_id and session_id:
                sessions.add(f"{user_id}:{session_id}")
            
            # Track agents
            agent_name = span.get('agent_name')
            if agent_name:
                agents.add(agent_name)
            
            # Track tools from metadata
            metadata = span.get('metadata', {})
            if 'tool_used' in metadata:
                tools.add(metadata['tool_used'])
            
            # Track errors
            if span.get('status') == 'ERROR':
                errors += 1
            
            # Track durations
            duration = span.get('duration_ms')
            if duration:
                durations.append(duration)
    
    total_requests = len(sessions)
    total_interactions = len(valid_spans)
    error_rate = errors / max(total_interactions, 1)
    avg_response_time = sum(durations) / len(durations) if durations else 0
    
    return {
        "total_requests": total_requests,
        "total_interactions": total_interactions,
        "error_rate": error_rate,
        "avg_response_time": avg_response_time,
        "active_agents": len(agents),
        "tools_used": len(tools),
        "period_hours": hours
    }


@router.get("/charts/request-timeline")
async def get_request_timeline_chart(hours: int = Query(24, ge=1, le=168)) -> Dict[str, Any]:
    """Get data for request timeline chart using Redis telemetry"""
    
    recent_spans = redis_client.zrange('telemetry:recent_spans', 0, -1)
    cutoff_time = datetime.now() - timedelta(hours=hours)
    
    # Group by hour
    timeline_data = {}
    sessions_by_hour = {}
    
    for span_id in recent_spans:
        span_data = redis_client.get(f'telemetry:span:{span_id}')
        if not span_data:
            continue
            
        span = json.loads(span_data)
        span_time = datetime.fromtimestamp(span['start_time'])
        
        if span_time >= cutoff_time:
            hour = span_time.replace(minute=0, second=0, microsecond=0)
            hour_key = hour.isoformat()
            
            # Track unique sessions per hour
            user_id = span.get('user_id')
            session_id = span.get('session_id')
            if user_id and session_id:
                session_key = f"{user_id}:{session_id}"
                if hour_key not in sessions_by_hour:
                    sessions_by_hour[hour_key] = set()
                sessions_by_hour[hour_key].add(session_key)
    
    # Convert to timeline data
    for hour_key, sessions in sessions_by_hour.items():
        timeline_data[hour_key] = len(sessions)
    
    current_time = datetime.now().replace(minute=0, second=0, microsecond=0)
    data_points = []
    
    for i in range(hours):
        hour = current_time - timedelta(hours=i)
        hour_key = hour.isoformat()
        data_points.append({
            "timestamp": hour_key,
            "requests": timeline_data.get(hour_key, 0),
            "hour_label": hour.strftime("%H:00")
        })
    
    return {
        "data": sorted(data_points, key=lambda x: x["timestamp"]),
        "total_requests": sum(d["requests"] for d in data_points)
    }


@router.get("/charts/agent-performance")
async def get_agent_performance_chart(hours: int = Query(24, ge=1, le=168)) -> Dict[str, Any]:
    """Get data for agent performance chart using Redis telemetry"""
    
    recent_spans = redis_client.zrange('telemetry:recent_spans', 0, -1)
    
    if not recent_spans:
        return {"data": [], "total_agents": 0}
    
    cutoff_time = datetime.now() - timedelta(hours=hours)
    agent_stats = {}
    
    for span_id in recent_spans:
        span_data = redis_client.get(f'telemetry:span:{span_id}')
        if not span_data:
            continue
            
        span = json.loads(span_data)
        span_time = datetime.fromtimestamp(span['start_time'])
        
        if span_time < cutoff_time:
            continue
            
        agent = span.get('agent_name')
        if not agent:
            continue
            
        if agent not in agent_stats:
            agent_stats[agent] = {
                "agent_name": agent,
                "total_interactions": 0,
                "errors": 0,
                "total_execution_time": 0,
                "execution_count": 0,
                "tools_used": set()
            }
        
        stats = agent_stats[agent]
        stats["total_interactions"] += 1
        
        if span.get('status') == 'ERROR':
            stats["errors"] += 1
        
        duration = span.get('duration_ms')
        if duration:
            stats["total_execution_time"] += duration
            stats["execution_count"] += 1
        
        # Track tools from metadata
        metadata = span.get('metadata', {})
        if 'tool_used' in metadata:
            stats["tools_used"].add(metadata['tool_used'])
    
    chart_data = []
    for agent, stats in agent_stats.items():
        chart_data.append({
            "agent_name": agent,
            "total_interactions": stats["total_interactions"],
            "error_rate": stats["errors"] / max(stats["total_interactions"], 1),
            "avg_execution_time": stats["total_execution_time"] / max(stats["execution_count"], 1),
            "tools_count": len(stats["tools_used"]),
            "success_rate": 1 - (stats["errors"] / max(stats["total_interactions"], 1))
        })
    
    return {
        "data": chart_data,
        "total_agents": len(chart_data)
    }


@router.get("/charts/tool-usage")
async def get_tool_usage_chart(hours: int = Query(24, ge=1, le=168)) -> Dict[str, Any]:
    """Get data for tool usage pie chart using Redis telemetry"""
    
    recent_spans = redis_client.zrange('telemetry:recent_spans', 0, -1)
    cutoff_time = datetime.now() - timedelta(hours=hours)
    
    tool_stats = {}
    
    for span_id in recent_spans:
        span_data = redis_client.get(f'telemetry:span:{span_id}')
        if not span_data:
            continue
            
        span = json.loads(span_data)
        span_time = datetime.fromtimestamp(span['start_time'])
        
        if span_time < cutoff_time:
            continue
        
        metadata = span.get('metadata', {})
        tool = metadata.get('tool_used')
        
        if not tool:
            continue
            
        if tool not in tool_stats:
            tool_stats[tool] = {
                "tool_name": tool,
                "usage_count": 0,
                "total_execution_time": 0,
                "success_count": 0,
                "failure_count": 0,
                "agents_using": set()
            }
        
        stats = tool_stats[tool]
        stats["usage_count"] += 1
        stats["agents_using"].add(span.get('agent_name'))
        
        duration = span.get('duration_ms')
        if duration:
            stats["total_execution_time"] += duration
        
        # Check success/failure based on status
        if span.get('status') == 'ERROR':
            stats["failure_count"] += 1
        else:
            stats["success_count"] += 1
    
    chart_data = []
    for tool, stats in tool_stats.items():
        chart_data.append({
            "tool_name": tool,
            "usage_count": stats["usage_count"],
            "avg_execution_time": stats["total_execution_time"] / max(stats["usage_count"], 1),
            "success_rate": stats["success_count"] / max(stats["usage_count"], 1),
            "agents_count": len(stats["agents_using"]),
            "percentage": 0  # Will be calculated on frontend
        })
    
    # Calculate percentages
    total_usage = sum(tool["usage_count"] for tool in chart_data)
    for tool in chart_data:
        tool["percentage"] = (tool["usage_count"] / max(total_usage, 1)) * 100
    
    return {
        "data": sorted(chart_data, key=lambda x: x["usage_count"], reverse=True),
        "total_tools": len(chart_data),
        "total_usage": total_usage
    }


@router.get("/charts/error-analysis")
async def get_error_analysis_chart(hours: int = Query(24, ge=1, le=168)) -> Dict[str, Any]:
    """Get data for error analysis chart using Redis telemetry"""
    
    recent_spans = redis_client.zrange('telemetry:recent_spans', 0, -1)
    cutoff_time = datetime.now() - timedelta(hours=hours)
    
    error_stats = {}
    
    for span_id in recent_spans:
        span_data = redis_client.get(f'telemetry:span:{span_id}')
        if not span_data:
            continue
            
        span = json.loads(span_data)
        span_time = datetime.fromtimestamp(span['start_time'])
        
        if span_time < cutoff_time or span.get('status') != 'ERROR':
            continue
        
        agent = span.get('agent_name', 'Unknown')
        error_type = span.get('metadata', {}).get('error_type', 'General Error')
        
        if agent not in error_stats:
            error_stats[agent] = {}
        
        if error_type not in error_stats[agent]:
            error_stats[agent][error_type] = {
                "count": 0,
                "recent_errors": []
            }
        
        error_stats[agent][error_type]["count"] += 1
        error_stats[agent][error_type]["recent_errors"].append({
            "timestamp": span_time.isoformat(),
            "message": span.get('metadata', {}).get('error_message', 'Unknown error')
        })
    
    chart_data = []
    for agent, errors in error_stats.items():
        for error_type, data in errors.items():
            chart_data.append({
                "agent_name": agent,
                "error_type": error_type,
                "count": data["count"],
                "recent_errors": data["recent_errors"][-5:]  # Last 5 errors
            })
    
    return {
        "data": sorted(chart_data, key=lambda x: x["count"], reverse=True),
        "total_errors": sum(item["count"] for item in chart_data),
        "affected_agents": len(error_stats)
    }


@router.get("/workflow/requests")
async def get_workflow_requests(
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(50, ge=1, le=200),
    user_id: Optional[str] = Query(None, description="Filter by user ID")
) -> Dict[str, Any]:
    """Get requests for workflow visualization using Redis telemetry data"""
    
    # Get all recent spans from Redis
    recent_spans = redis_client.zrange('telemetry:recent_spans', 0, -1)
    
    if not recent_spans:
        return {"requests": [], "total": 0}
    
    # Group spans by session to create workflows
    workflows = {}
    cutoff_time = datetime.now() - timedelta(hours=hours)
    
    for span_id in recent_spans:
        span_data = redis_client.get(f'telemetry:span:{span_id}')
        if not span_data:
            continue
            
        span = json.loads(span_data)
        span_time = datetime.fromtimestamp(span['start_time'])
        
        if span_time < cutoff_time:
            continue
            
        span_user_id = span.get('user_id')
        span_session_id = span.get('session_id')
        
        # Apply user filter
        if user_id and str(span_user_id) != user_id:
                continue
            
        workflow_key = f"{span_user_id}:{span_session_id}"
        
        if workflow_key not in workflows:
            workflows[workflow_key] = {
                "id": workflow_key,
                "user_id": str(span_user_id) if span_user_id else "unknown",
                "session_id": span_session_id,
                "spans": [],
                "agents_involved": set(),
                "tools_used": set(),
                "start_time": span_time,
                "end_time": span_time,
                "has_errors": False,
                "user_message": "Healthcare workflow request"  # Default, will be updated if found
            }
        
        workflow = workflows[workflow_key]
        workflow["spans"].append(span)
        workflow["agents_involved"].add(span.get('agent_name'))
        
        # Update user_message if this span has one in metadata (prioritize actual user messages)
        span_user_message = span.get('metadata', {}).get('user_message')
        if span_user_message and span_user_message != "Healthcare workflow request":
            workflow["user_message"] = span_user_message
        
        # Track tools
        metadata = span.get('metadata', {})
        if 'tool_used' in metadata:
            workflow["tools_used"].add(metadata['tool_used'])
        
        # Update time bounds
        if span_time < workflow["start_time"]:
            workflow["start_time"] = span_time
        if span_time > workflow["end_time"]:
            workflow["end_time"] = span_time
            
        # Check for errors
        if span.get('status') == 'ERROR':
            workflow["has_errors"] = True
    
    # Convert to the format expected by the frontend
    requests_data = []
    for workflow_data in sorted(workflows.values(), 
                               key=lambda x: x["start_time"], 
                               reverse=True)[:limit]:
        
        duration_ms = (workflow_data["end_time"] - workflow_data["start_time"]).total_seconds() * 1000
        
        requests_data.append({
            "id": workflow_data["id"],
            "timestamp": workflow_data["start_time"].isoformat(),
            "user_message": workflow_data["user_message"],
            "user_id": workflow_data["user_id"],
            "agents_involved": list(workflow_data["agents_involved"]),
            "tools_used": list(workflow_data["tools_used"]),
            "total_events": len(workflow_data["spans"]),
            "duration_ms": duration_ms,
            "has_errors": workflow_data["has_errors"],
            "status": "error" if workflow_data["has_errors"] else "success"
        })
    
    return {
        "requests": requests_data,
        "total": len(requests_data)
    }


@router.get("/workflow/request/{request_id}")
async def get_request_workflow_detail(request_id: str) -> Dict[str, Any]:
    """Get detailed workflow information for a specific request using Redis telemetry with hierarchy support"""
    
    # Parse request_id to get user_id and session_id
    try:
        user_id_str, session_id_str = request_id.split(":", 1)
        user_id = int(user_id_str)
        session_id = int(session_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid request_id format")
    
    recent_spans = redis_client.zrange('telemetry:recent_spans', 0, -1)
    workflow_spans = []
    
    for span_id in recent_spans:
        span_data = redis_client.get(f'telemetry:span:{span_id}')
        if not span_data:
            continue
            
        span = json.loads(span_data)
        
        if (span.get('user_id') == user_id and 
            span.get('session_id') == session_id):
            workflow_spans.append(span)
    
    if not workflow_spans:
        raise HTTPException(status_code=404, detail="Request not found")
    
    # Sort spans by timestamp
    workflow_spans.sort(key=lambda x: x['start_time'])
    
    # Build hierarchical structure
    hierarchical_lineage = _build_hierarchical_lineage(workflow_spans)
    
    # Build traditional lineage/flow for backward compatibility
    lineage = []
    agents_involved = set()
    tools_used = set()
    total_duration = 0
    has_errors = False
    
    for span in workflow_spans:
        agents_involved.add(span.get('agent_name'))
        
        metadata = span.get('metadata', {})
        if 'tool_used' in metadata:
            tools_used.add(metadata['tool_used'])
        
        if span.get('duration_ms'):
            total_duration += span['duration_ms']
        
        if span.get('status') == 'ERROR':
            has_errors = True
        
        lineage.append({
            "span_id": span.get('span_id'),
            "agent_name": span.get('agent_name'),
            "operation": span.get('operation_name', 'Unknown'),
            "timestamp": datetime.fromtimestamp(span['start_time']).isoformat(),
            "duration_ms": span.get('duration_ms', 0),
            "status": span.get('status', 'UNKNOWN'),
            "metadata": metadata,
            "parent_span_id": span.get('parent_span_id'),  # NEW
            "orchestrator": span.get('orchestrator')       # NEW
        })
    
    return {
        "request_id": request_id,
        "user_id": user_id,
        "session_id": session_id,
        "lineage": lineage,
        "hierarchical_lineage": hierarchical_lineage,  # NEW: Hierarchical view
        "summary": {
            "total_steps": len(workflow_spans),
            "agents_involved": list(agents_involved),
            "tools_used": list(tools_used),
            "total_duration_ms": total_duration,
            "status": "error" if has_errors else "success",
            "start_time": datetime.fromtimestamp(workflow_spans[0]['start_time']).isoformat(),
            "end_time": datetime.fromtimestamp(workflow_spans[-1]['start_time']).isoformat()
        }
    }


def _build_hierarchical_lineage(spans: List[Dict]) -> List[Dict]:
    """Build hierarchical representation of workflow spans"""
    
    # Create span lookup
    span_lookup = {span['span_id']: span for span in spans}
    
    # Find root spans (no parent)
    root_spans = [span for span in spans if not span.get('parent_span_id')]
    
    def build_tree_node(span: Dict) -> Dict:
        """Recursively build tree structure"""
        metadata = span.get('metadata', {})
        
        # Extract meaningful message content from metadata
        message_content = {}
        
        # Extract user messages
        if metadata.get('user_message'):
            message_content['user_message'] = metadata['user_message']
        
        # Extract operation-specific content
        if metadata.get('operation_type'):
            message_content['operation_type'] = metadata['operation_type']
        
        # Extract agent responses
        if metadata.get('success') is not None:
            message_content['success'] = metadata['success']
        
        # Extract error information
        if metadata.get('error'):
            message_content['error'] = metadata['error']
        
        # Extract data summaries
        if metadata.get('message_type'):
            message_content['message_type'] = metadata['message_type']
        
        # Extract guardrails information
        if metadata.get('violations'):
            message_content['guardrails_violations'] = len(metadata['violations'])
        
        if metadata.get('is_safe') is not None:
            message_content['guardrails_safe'] = metadata['is_safe']
        
        # Extract medical/health data summaries
        if metadata.get('tests_extracted'):
            message_content['tests_extracted'] = metadata['tests_extracted']
        
        if metadata.get('abnormal_tests'):
            message_content['abnormal_tests'] = metadata['abnormal_tests']
        
        # Extract coordination information
        if metadata.get('coordination_mode'):
            message_content['coordination_mode'] = metadata['coordination_mode']
        
        if metadata.get('total_agents_used'):
            message_content['agents_used'] = metadata['total_agents_used']
        
        # Extract classification/routing information
        if metadata.get('classified_domain'):
            message_content['classified_domain'] = metadata['classified_domain']
        
        if metadata.get('routing_time'):
            message_content['routing_time'] = f"{metadata['routing_time']:.3f}s"
        
        node = {
            "span_id": span['span_id'],
            "agent_name": span.get('agent_name'),
            "operation": span.get('operation_name', 'Unknown'),
            "timestamp": datetime.fromtimestamp(span['start_time']).isoformat(),
            "duration_ms": span.get('duration_ms', 0),
            "status": span.get('status', 'UNKNOWN'),
            "metadata": metadata,
            "message_content": message_content,  # NEW: Structured message content
            "orchestrator": span.get('orchestrator'),
            "children": []
        }
        
        # Find child spans
        child_spans = [
            s for s in spans 
            if s.get('parent_span_id') == span['span_id']
        ]
        
        # Sort children by timestamp
        child_spans.sort(key=lambda x: x['start_time'])
        
        # Recursively build children
        for child_span in child_spans:
            child_node = build_tree_node(child_span)
            node["children"].append(child_node)
        
        return node
    
    # Build hierarchical structure
    hierarchical_structure = []
    
    # Sort root spans by timestamp
    root_spans.sort(key=lambda x: x['start_time'])
    
    for root_span in root_spans:
        tree_node = build_tree_node(root_span)
        hierarchical_structure.append(tree_node)
    
    return hierarchical_structure


@router.get("/workflow/request/{request_id}/messages")
async def get_request_inter_agent_messages(request_id: str) -> Dict[str, Any]:
    """Get inter-agent messages for a specific request using Redis telemetry"""
    
    # Parse request_id to get user_id and session_id
    try:
        user_id_str, session_id_str = request_id.split(":", 1)
        user_id = int(user_id_str)
        session_id = int(session_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid request_id format")
    
    recent_spans = redis_client.zrange('telemetry:recent_spans', 0, -1)
    messages = []
    
    for span_id in recent_spans:
        span_data = redis_client.get(f'telemetry:span:{span_id}')
        if not span_data:
            continue
            
        span = json.loads(span_data)
        
        if (span.get('user_id') == user_id and 
            span.get('session_id') == session_id):
            
            metadata = span.get('metadata', {})
            
            # Extract messages from metadata
            if 'input_message' in metadata:
                messages.append({
                    "timestamp": datetime.fromtimestamp(span['start_time']).isoformat(),
                    "from_agent": "User",
                    "to_agent": span.get('agent_name'),
                    "message_type": "input",
                    "content": metadata['input_message'],
                    "span_id": span.get('span_id')
                })
            
            if 'output_message' in metadata:
                messages.append({
                    "timestamp": datetime.fromtimestamp(span['start_time']).isoformat(),
                    "from_agent": span.get('agent_name'),
                    "to_agent": "User",
                    "message_type": "output",
                    "content": metadata['output_message'],
                    "span_id": span.get('span_id')
                })
            
            if 'inter_agent_message' in metadata:
                messages.append({
                    "timestamp": datetime.fromtimestamp(span['start_time']).isoformat(),
                    "from_agent": span.get('agent_name'),
                    "to_agent": metadata.get('target_agent', 'Unknown'),
                    "message_type": "inter_agent",
                    "content": metadata['inter_agent_message'],
                    "span_id": span.get('span_id')
                })
    
    # Sort messages by timestamp
    messages.sort(key=lambda x: x['timestamp'])
    
    return {
        "request_id": request_id,
        "messages": messages,
        "total_messages": len(messages)
    }


@router.get("/monitoring/system-health")
async def get_system_health() -> Dict[str, Any]:
    """Get current system health status using system metrics"""
    from app.core.system_metrics import system_metrics
    
    # Get actual system health with CPU, memory, disk metrics
    return await system_metrics.get_system_health()


def get_real_time_metrics() -> Dict[str, Any]:
    """Get real-time metrics for WebSocket updates"""
    last_10_minutes = datetime.now() - timedelta(minutes=10)
    recent_spans = redis_client.zrange('telemetry:recent_spans', -50, -1)  # Last 50 spans
    
    active_sessions = set()
    active_agents = set()
    recent_errors = 0
    
    for span_id in recent_spans:
        span_data = redis_client.get(f'telemetry:span:{span_id}')
        if not span_data:
            continue
            
        span = json.loads(span_data)
        span_time = datetime.fromtimestamp(span['start_time'])
        
        if span_time >= last_10_minutes:
            user_id = span.get('user_id')
            session_id = span.get('session_id')
            if user_id and session_id:
                active_sessions.add(f"{user_id}:{session_id}")
            
            agent_name = span.get('agent_name')
            if agent_name:
                active_agents.add(agent_name)
            
            if span.get('status') == 'ERROR':
                recent_errors += 1
    
    return {
        "active_sessions": len(active_sessions),
        "active_agents": len(active_agents),
        "recent_errors": recent_errors,
        "timestamp": datetime.now().isoformat()
    }


def get_recent_activity(limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent activity for WebSocket updates"""
    recent_spans = redis_client.zrange('telemetry:recent_spans', -limit, -1)
    
    activities = []
    for span_id in recent_spans:
        span_data = redis_client.get(f'telemetry:span:{span_id}')
        if not span_data:
            continue
            
        span = json.loads(span_data)
        activities.append({
            "timestamp": datetime.fromtimestamp(span['start_time']).isoformat(),
            "agent_name": span.get('agent_name'),
            "operation": span.get('operation_name', 'Unknown'),
            "status": span.get('status', 'UNKNOWN'),
            "user_id": span.get('user_id')
        })
    
    return sorted(activities, key=lambda x: x['timestamp'], reverse=True) 