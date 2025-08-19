"""
Audit Trail API Endpoints for Agent Interactions
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel
import json

from app.core.agent_logger import agent_logger, EventType, LogLevel

router = APIRouter(prefix="/audit", tags=["audit"])

class UserSessionRequest(BaseModel):
    user_id: str
    session_id: Optional[str] = None

class MessageLineageResponse(BaseModel):
    session_id: str
    message_flow: List[Dict[str, Any]]
    agent_handoffs: List[Dict[str, Any]]
    processing_timeline: List[Dict[str, Any]]
    error_events: List[Dict[str, Any]]

class SessionSummaryResponse(BaseModel):
    session_id: str
    agents_involved: List[str]
    total_messages: int
    total_errors: int
    total_processing_time_ms: float
    session_duration: int
    start_time: Optional[str]
    end_time: Optional[str]

@router.get("/request/{request_id}")
async def get_request_lineage(request_id: str):
    """Get complete audit trail for a specific request"""
    try:
        lineage = agent_logger.get_request_lineage(request_id)
        
        if not lineage:
            raise HTTPException(status_code=404, detail="Request not found")
        
        return {
            "request_id": request_id,
            "total_events": len(lineage),
            "events": [
                {
                    "timestamp": entry.timestamp,
                    "event_type": entry.event_type.value,
                    "agent_name": entry.agent_name,
                    "operation": entry.operation,
                    "details": entry.details,
                    "execution_time_ms": entry.execution_time_ms,
                    "lineage_path": entry.lineage_path
                }
                for entry in lineage
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving request lineage: {str(e)}")

@router.get("/user-session/{session_id}")
async def get_user_session_lineage(session_id: str):
    """Get complete audit trail for a user session"""
    try:
        lineage = agent_logger.get_user_session_lineage(session_id)
        
        if not lineage:
            raise HTTPException(status_code=404, detail="User session not found")
        
        return {
            "session_id": session_id,
            "total_events": len(lineage),
            "events": [
                {
                    "timestamp": entry.timestamp,
                    "event_type": entry.event_type.value,
                    "agent_name": entry.agent_name,
                    "source_agent": entry.source_agent,
                    "target_agent": entry.target_agent,
                    "operation": entry.operation,
                    "message_content": entry.message_content,
                    "details": entry.details,
                    "execution_time_ms": entry.execution_time_ms,
                    "lineage_path": entry.lineage_path
                }
                for entry in lineage
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving session lineage: {str(e)}")

@router.get("/message-lineage/{session_id}", response_model=MessageLineageResponse)
async def get_message_lineage(session_id: str):
    """Get detailed message lineage for audit purposes"""
    try:
        # Get session logs
        session_logs = [log for log in agent_logger.interaction_log if log.session_id == session_id]
        
        if not session_logs:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Build lineage from available logs
        lineage = {
            "session_id": session_id,
            "message_flow": [],
            "agent_handoffs": [],
            "processing_timeline": [],
            "error_events": []
        }
        
        for log in session_logs:
            if log.event_type == EventType.INTER_AGENT_MESSAGE:
                lineage["message_flow"].append({
                    "timestamp": log.timestamp,
                    "from": log.source_agent or log.agent_name,
                    "to": log.target_agent or "Unknown",
                    "content_preview": log.message_content or log.message,
                    "metadata": log.message_metadata or {}
                })
            
            elif log.event_type == EventType.AGENT_HANDOFF:
                lineage["agent_handoffs"].append({
                    "timestamp": log.timestamp,
                    "from": log.source_agent or log.agent_name,
                    "to": log.target_agent or "Unknown",
                    "lineage_path": log.lineage_path or []
                })
            
            elif log.event_type in [EventType.AGENT_PROCESSING, EventType.AGENT_CATEGORIZATION]:
                lineage["processing_timeline"].append({
                    "timestamp": log.timestamp,
                    "agent": log.agent_name,
                    "operation": log.event_type.value,
                    "execution_time_ms": log.execution_time_ms
                })
            
            elif log.event_type == EventType.ERROR:
                lineage["error_events"].append({
                    "timestamp": log.timestamp,
                    "agent": log.agent_name,
                    "error_details": log.error_details or {"message": log.message}
                })
        
        return MessageLineageResponse(**lineage)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving message lineage: {str(e)}")

@router.get("/session-summary/{session_id}", response_model=SessionSummaryResponse)
async def get_session_summary(session_id: str):
    """Get summary statistics for a user session"""
    try:
        summary = agent_logger.get_session_summary(session_id)
        
        if "error" in summary:
            raise HTTPException(status_code=404, detail=summary["error"])
        
        return SessionSummaryResponse(**summary)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving session summary: {str(e)}")

@router.get("/user-sessions")
async def get_user_sessions(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    start_time: Optional[datetime] = Query(None, description="Start time filter"),
    end_time: Optional[datetime] = Query(None, description="End time filter"),
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of sessions to return")
):
    """Get list of user sessions with optional filtering"""
    try:
        # Get all logs from the current logger
        all_logs = agent_logger.interaction_log
        
        # Extract unique sessions with enhanced data
        sessions = {}
        for log in all_logs:
            if log.session_id and log.session_id != "no-session":
                session_id = log.session_id
                if session_id not in sessions:
                    sessions[session_id] = {
                        "session_id": session_id,
                        "user_id": str(log.user_id) if log.user_id else None,
                        "start_time": log.timestamp,
                        "end_time": None,
                        "total_messages": 0,
                        "agents_involved": set(),
                        "session_status": "active"
                    }
                
                # Update end time with latest timestamp
                sessions[session_id]["end_time"] = log.timestamp
                
                # Count messages and track agents
                if log.event_type == EventType.INTER_AGENT_MESSAGE:
                    sessions[session_id]["total_messages"] += 1
                
                if log.agent_name:
                    sessions[session_id]["agents_involved"].add(log.agent_name)
                if hasattr(log, 'source_agent') and log.source_agent:
                    sessions[session_id]["agents_involved"].add(log.source_agent)
                if hasattr(log, 'target_agent') and log.target_agent:
                    sessions[session_id]["agents_involved"].add(log.target_agent)
        
        # Filter by user_id if provided
        if user_id:
            sessions = {k: v for k, v in sessions.items() if v.get("user_id") == user_id}
        
        # Convert sets to lists and determine session status
        for session in sessions.values():
            session["agents_involved"] = list(session["agents_involved"])
            # Determine session status based on recent activity (simple heuristic)
            if session["end_time"]:
                time_since_last_activity = datetime.now(timezone.utc) - session["end_time"]
                if time_since_last_activity.total_seconds() > 3600:  # 1 hour
                    session["session_status"] = "completed"
                else:
                    session["session_status"] = "active"
        
        # Convert to list and limit
        session_list = list(sessions.values())[:limit]
        
        return {
            "total_sessions": len(session_list),
            "sessions": session_list
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving user sessions: {str(e)}")

@router.get("/agent-interactions")
async def get_agent_interactions(
    user_session_id: Optional[str] = Query(None, description="Filter by user session"),
    agent_name: Optional[str] = Query(None, description="Filter by agent name"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    start_time: Optional[datetime] = Query(None, description="Start time filter"),
    end_time: Optional[datetime] = Query(None, description="End time filter"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of interactions to return")
):
    """Get agent interactions with filtering options"""
    try:
        interactions = agent_logger.get_agent_interactions(
            user_session_id=user_session_id,
            start_time=start_time,
            end_time=end_time
        )
        
        # Apply additional filters
        if agent_name:
            interactions = [i for i in interactions if i.agent_name == agent_name]
        
        if event_type:
            try:
                event_filter = EventType(event_type)
                interactions = [i for i in interactions if i.event_type == event_filter]
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid event_type: {event_type}")
        
        # Limit results
        interactions = interactions[:limit]
        
        return {
            "total_interactions": len(interactions),
            "interactions": [
                {
                    "timestamp": entry.timestamp,
                    "request_id": entry.request_id,
                    "user_session_id": entry.user_session_id,
                    "event_type": entry.event_type.value,
                    "agent_name": entry.agent_name,
                    "source_agent": entry.source_agent,
                    "target_agent": entry.target_agent,
                    "operation": entry.operation,
                    "message_content": entry.message_content[:200] if entry.message_content else None,
                    "execution_time_ms": entry.execution_time_ms,
                    "lineage_path": entry.lineage_path
                }
                for entry in interactions
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving agent interactions: {str(e)}")

@router.get("/agent-performance")
async def get_agent_performance(
    time_range: int = Query(24, description="Time range in hours"),
    agent_name: Optional[str] = Query(None, description="Filter by specific agent")
):
    """Get agent performance metrics with message flow analysis"""
    try:
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=time_range)
        
        interactions = agent_logger.get_agent_interactions(start_time=start_time, end_time=end_time)
        
        # Filter by agent if specified
        if agent_name:
            interactions = [i for i in interactions if i.agent_name == agent_name]
        
        # Calculate metrics per agent
        agent_stats = {}
        for interaction in interactions:
            if not interaction.agent_name:
                continue
                
            agent = interaction.agent_name
            if agent not in agent_stats:
                agent_stats[agent] = {
                    "agent_name": agent,
                    "total_interactions": 0,
                    "messages_sent": 0,
                    "messages_received": 0,
                    "errors": 0,
                    "avg_execution_time": 0,
                    "total_execution_time": 0,
                    "handoffs_initiated": 0,
                    "handoffs_received": 0
                }
            
            stats = agent_stats[agent]
            stats["total_interactions"] += 1
            
            if interaction.event_type == EventType.INTER_AGENT_MESSAGE:
                if interaction.source_agent == agent:
                    stats["messages_sent"] += 1
                if interaction.target_agent == agent:
                    stats["messages_received"] += 1
            
            if interaction.event_type == EventType.AGENT_HANDOFF:
                if interaction.source_agent == agent:
                    stats["handoffs_initiated"] += 1
                if interaction.target_agent == agent:
                    stats["handoffs_received"] += 1
            
            if interaction.event_type == EventType.ERROR:
                stats["errors"] += 1
            
            if interaction.execution_time_ms:
                stats["total_execution_time"] += interaction.execution_time_ms
        
        # Calculate averages
        for stats in agent_stats.values():
            if stats["total_interactions"] > 0:
                stats["avg_execution_time"] = stats["total_execution_time"] / stats["total_interactions"]
                stats["error_rate"] = stats["errors"] / stats["total_interactions"]
            else:
                stats["error_rate"] = 0
        
        return {
            "time_range_hours": time_range,
            "total_agents": len(agent_stats),
            "agent_performance": list(agent_stats.values())
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving agent performance: {str(e)}")

@router.get("/message-flow-diagram/{session_id}")
async def get_message_flow_diagram(session_id: str):
    """Get data for visualizing message flow between agents"""
    try:
        lineage = agent_logger.get_message_lineage(session_id)
        
        if "error" in lineage:
            raise HTTPException(status_code=404, detail=lineage["error"])
        
        # Extract nodes (agents) and edges (messages/handoffs)
        nodes = set()
        edges = []
        
        # Process message flows
        for msg in lineage["message_flow"]:
            nodes.add(msg["from"])
            nodes.add(msg["to"])
            edges.append({
                "from": msg["from"],
                "to": msg["to"],
                "type": "message",
                "timestamp": msg["timestamp"],
                "content_preview": msg["content_preview"]
            })
        
        # Process handoffs
        for handoff in lineage["agent_handoffs"]:
            nodes.add(handoff["from"])
            nodes.add(handoff["to"])
            edges.append({
                "from": handoff["from"],
                "to": handoff["to"],
                "type": "handoff",
                "timestamp": handoff["timestamp"],
                "lineage_path": handoff["lineage_path"]
            })
        
        return {
            "session_id": session_id,
            "nodes": [{"id": node, "label": node} for node in nodes],
            "edges": edges,
            "flow_summary": {
                "total_messages": len(lineage["message_flow"]),
                "total_handoffs": len(lineage["agent_handoffs"]),
                "unique_agents": len(nodes)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating message flow diagram: {str(e)}")

@router.get("/compliance-report/{session_id}")
async def get_compliance_report(session_id: str):
    """Generate compliance report for audit purposes"""
    try:
        lineage = agent_logger.get_message_lineage(session_id)
        summary = agent_logger.get_session_summary(session_id)
        
        if "error" in lineage or "error" in summary:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Generate compliance metrics
        compliance_report = {
            "session_id": session_id,
            "audit_timestamp": datetime.now(timezone.utc).isoformat(),
            "session_summary": summary,
            "data_lineage": lineage,
            "compliance_metrics": {
                "message_traceability": "COMPLETE" if lineage["message_flow"] else "INCOMPLETE",
                "agent_accountability": "TRACKED" if lineage["agent_handoffs"] else "LIMITED",
                "error_handling": "DOCUMENTED" if lineage["error_events"] else "CLEAN_SESSION",
                "processing_transparency": "FULL" if lineage["processing_timeline"] else "LIMITED"
            },
            "audit_trail_completeness": {
                "has_message_flow": len(lineage["message_flow"]) > 0,
                "has_handoff_tracking": len(lineage["agent_handoffs"]) > 0,
                "has_processing_timeline": len(lineage["processing_timeline"]) > 0,
                "has_error_documentation": len(lineage["error_events"]) > 0
            }
        }
        
        return compliance_report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating compliance report: {str(e)}")

@router.get("/recent-activity")
async def get_recent_activity(
    limit: int = Query(50, ge=1, le=500, description="Number of recent activities to return"),
    event_types: Optional[str] = Query(None, description="Comma-separated event types to filter")
):
    """Get recent agent activities across all sessions"""
    try:
        # Get recent interactions (last 24 hours by default)
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=24)
        
        interactions = agent_logger.get_agent_interactions(start_time=start_time, end_time=end_time)
        
        # Filter by event types if provided
        if event_types:
            try:
                event_filter = [EventType(et.strip()) for et in event_types.split(",")]
                interactions = [i for i in interactions if i.event_type in event_filter]
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid event_type: {str(e)}")
        
        # Sort by timestamp (most recent first) and limit
        interactions.sort(key=lambda x: x.timestamp, reverse=True)
        interactions = interactions[:limit]
        
        return {
            "total_activities": len(interactions),
            "activities": [
                {
                    "timestamp": entry.timestamp,
                    "event_type": entry.event_type.value,
                    "agent_name": entry.agent_name,
                    "operation": entry.operation,
                    "user_session_id": entry.user_session_id,
                    "details": entry.details,
                    "execution_time_ms": entry.execution_time_ms
                }
                for entry in interactions
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving recent activity: {str(e)}")

@router.get("/debug/logs")
async def get_debug_logs():
    """Debug endpoint to see current logged data"""
    try:
        logs = agent_logger.interaction_log
        return {
            "total_logs": len(logs),
            "logs": [
                {
                    "timestamp": log.timestamp,
                    "session_id": log.session_id,
                    "agent_name": log.agent_name,
                    "event_type": log.event_type.value,
                    "message": log.message,
                    "user_id": log.user_id
                }
                for log in logs[-10:]  # Last 10 logs
            ]
        }
    except Exception as e:
        return {"error": str(e), "logs": []}

 