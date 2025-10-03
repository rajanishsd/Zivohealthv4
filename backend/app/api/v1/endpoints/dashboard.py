from fastapi import APIRouter, Depends, HTTPException
from typing import Any, Dict, List
from app.api.deps import get_db
from sqlalchemy.orm import Session
from app.api import deps
from app.routes import dashboard as legacy_dashboard
from datetime import datetime, timedelta

router = APIRouter()


def _require_admin(current=Depends(deps.get_current_user_or_doctor)):
    from app.models import Admin
    if not isinstance(current, Admin):
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return current


@router.get("/metrics/overview")
async def metrics_overview(current=Depends(_require_admin)) -> Any:
    return await legacy_dashboard.get_overview_metrics()


@router.get("/workflow/requests")
async def workflow_requests(hours: int = 24, limit: int = 100, current=Depends(_require_admin)) -> Any:
    return await legacy_dashboard.get_workflow_requests(hours=hours, limit=limit)


@router.get("/system-health")
async def system_health(current=Depends(_require_admin)) -> Any:
    # Reuse legacy system health generator
    return await legacy_dashboard.get_system_health()


@router.get("/chat-sessions/statistics")
async def chat_sessions_statistics(hours: int = 24, limit: int = 100, current=Depends(_require_admin)) -> Dict[str, Any]:
    """
    Admin-only chat sessions summary built from telemetry spans.
    Returns a structure compatible with the dashboard's expectations.
    """
    recent_spans = legacy_dashboard.redis_client.zrange('telemetry:recent_spans', 0, -1)
    if not recent_spans:
        return {"sessions": []}

    cutoff = legacy_dashboard.now_local() - timedelta(hours=hours)
    sessions = {}

    for span_id in recent_spans:
        span_data = legacy_dashboard.redis_client.get(f'telemetry:span:{span_id}')
        if not span_data:
            continue
        span = legacy_dashboard.json.loads(span_data)
        span_time = datetime.fromtimestamp(span.get('start_time', 0))
        if span_time < cutoff:
            continue
        user_id = span.get('user_id')
        session_id = span.get('session_id')
        if user_id is None or session_id is None:
            continue
        key = f"{user_id}:{session_id}"
        if key not in sessions:
            sessions[key] = {
                "session_id": session_id,
                "user_id": str(user_id),
                "start_time": span_time,
                "end_time": span_time,
                "total_messages": 0,
                "agents_involved": set(),
            }
        s = sessions[key]
        s["total_messages"] += 1
        s["agents_involved"].add(span.get('agent_name'))
        if span_time < s["start_time"]:
            s["start_time"] = span_time
        if span_time > s["end_time"]:
            s["end_time"] = span_time

    # Build response list
    result: List[Dict[str, Any]] = []
    now = legacy_dashboard.now_local()
    for s in sessions.values():
        status = "active" if (now - s["end_time"]) <= timedelta(minutes=5) else "completed"
        result.append({
            "session_id": s["session_id"],
            "user_id": s["user_id"],
            "start_time": s["start_time"].isoformat(),
            "end_time": s["end_time"].isoformat(),
            "total_messages": s["total_messages"],
            "agents_involved": [a for a in s["agents_involved"] if a],
            "session_status": status,
        })

    # Sort and limit
    result.sort(key=lambda x: x["start_time"], reverse=True)
    return {"sessions": result[:limit]}


