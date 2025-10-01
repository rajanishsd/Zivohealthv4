from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import verify_api_key_dependency
from .unified_schemas import ReminderCreate, ReminderRead, ReminderAck, DeviceTokenCreate, DeviceTokenRead, ReminderQueued, ReminderUpdate
from .unified_models import Reminder
from .repository import get_reminder, list_reminders, mark_acknowledged, upsert_device_token
from .unified_service import UnifiedReminderService
from .celery_app import celery_app
from .config import settings
from .metrics import reminders_created_total, reminders_acknowledged_total


router = APIRouter(dependencies=[Depends(verify_api_key_dependency)])


@router.post("/", response_model=ReminderQueued)
def create_reminder_endpoint(payload: ReminderCreate, db: Session = Depends(get_db)):
    # Validate payload shape early (FastAPI/Pydantic already validates types)
    if payload.recurrence_pattern:
        if not payload.start_date:
            raise HTTPException(status_code=400, detail="start_date is required for recurring reminders")
    if not payload.external_id:
        # Generate a deterministic external_id if client didn't send one
        # Format: userId:reminderType:epochSeconds
        epoch = int(payload.reminder_time.timestamp()) if payload.reminder_time else int(datetime.utcnow().timestamp())
        payload.external_id = f"{payload.user_id}:{payload.reminder_type}:{epoch}"

    # Enqueue for asynchronous creation; downstream will dedupe on external_id
    celery_app.send_task(
        "reminders.ingest",
        args=[payload.dict()],
        queue=settings.RABBITMQ_INPUT_QUEUE,
        routing_key=settings.RABBITMQ_INPUT_ROUTING_KEY,
    )
    return ReminderQueued(external_id=payload.external_id, queued_at=datetime.utcnow())


@router.patch("/{reminder_id}", response_model=ReminderRead)
def update_reminder_endpoint(reminder_id: str, payload: ReminderUpdate, db: Session = Depends(get_db)):
    """Update an existing reminder (supports both one-time and recurring)."""
    service = UnifiedReminderService(db)
    r = service.update_reminder(reminder_id, payload)
    if not r:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return ReminderRead(
        id=str(r.id),
        user_id=r.user_id,
        reminder_time=r.reminder_time,
        reminder_type=r.reminder_type,
        title=r.title,
        message=r.message,
        payload=r.payload,
        status=r.status,
        is_recurring=r.is_recurring,
        recurrence_pattern=r.recurrence_pattern,
        parent_reminder_id=str(r.parent_reminder_id) if getattr(r, "parent_reminder_id", None) else None,
        occurrence_number=r.occurrence_number,
        is_generated=r.is_generated,
        start_date=r.start_date,
        end_date=r.end_date,
        max_occurrences=r.max_occurrences,
        timezone=r.timezone,
        last_occurrence=r.last_occurrence,
        next_occurrence=r.next_occurrence,
        occurrence_count=r.occurrence_count,
        is_active=r.is_active,
        external_id=r.external_id,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


@router.delete("/{reminder_id}", status_code=204)
def delete_reminder_endpoint(reminder_id: str, db: Session = Depends(get_db)):
    """Delete a reminder by ID (supports both one-time and recurring templates)."""
    r = db.get(Reminder, reminder_id)
    if not r:
        raise HTTPException(status_code=404, detail="Reminder not found")
    db.delete(r)
    db.commit()
    return Response(status_code=204)


@router.get("/", response_model=List[ReminderRead])
def list_reminders_endpoint(
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    items = list_reminders(db, user_id=user_id, status=status, start=start, end=end, limit=limit)
    return [
        ReminderRead(
            id=str(i.id),
            user_id=i.user_id,
            reminder_type=i.reminder_type,
            title=getattr(i, "title", None),
            message=getattr(i, "message", None),
            payload=i.payload,
            reminder_time=i.reminder_time,
            status=i.status,
            external_id=getattr(i, "external_id", None),
            is_recurring=bool(getattr(i, "is_recurring", False)),
            recurrence_pattern=getattr(i, "recurrence_pattern", None),
            parent_reminder_id=str(getattr(i, "parent_reminder_id", "")) if getattr(i, "parent_reminder_id", None) else None,
            occurrence_number=getattr(i, "occurrence_number", None),
            is_generated=bool(getattr(i, "is_generated", False)),
            start_date=getattr(i, "start_date", None),
            end_date=getattr(i, "end_date", None),
            max_occurrences=getattr(i, "max_occurrences", None),
            timezone=getattr(i, "timezone", None),
            last_occurrence=getattr(i, "last_occurrence", None),
            next_occurrence=getattr(i, "next_occurrence", None),
            occurrence_count=int(getattr(i, "occurrence_count", 0)),
            is_active=bool(getattr(i, "is_active", True)),
            created_at=i.created_at,
            updated_at=i.updated_at,
        )
        for i in items
    ]


@router.get("/devices", response_model=List[DeviceTokenRead])
def list_device_tokens(
    user_id: Optional[str] = None,
    platform: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    from .repository import list_device_tokens as repo_list_device_tokens
    tokens = repo_list_device_tokens(db, user_id=user_id, platform=platform, limit=limit)
    return [
        DeviceTokenRead(
            id=str(t.id),
            user_id=t.user_id,
            platform=t.platform,
            fcm_token=t.fcm_token,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t in tokens
    ]


@router.post("/devices", response_model=DeviceTokenRead)
def register_device_token(payload: DeviceTokenCreate, db: Session = Depends(get_db)):
    t = upsert_device_token(db, payload)
    return DeviceTokenRead(
        id=str(t.id),
        user_id=t.user_id,
        platform=t.platform,
        fcm_token=t.fcm_token,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


@router.get("/health")
def health_check():
    return {"status": "healthy", "service": "reminders"}


@router.get("/{reminder_id}", response_model=ReminderRead)
def get_reminder_endpoint(reminder_id: str, db: Session = Depends(get_db)):
    r = get_reminder(db, reminder_id)
    if not r:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return ReminderRead(
        id=str(r.id),
        user_id=r.user_id,
        reminder_time=r.reminder_time,
        reminder_type=r.reminder_type,
        payload=r.payload,
        status=r.status,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


@router.post("/{reminder_id}/ack", response_model=ReminderAck)
def ack_reminder_endpoint(reminder_id: str, db: Session = Depends(get_db)):
    if not get_reminder(db, reminder_id):
        raise HTTPException(status_code=404, detail="Reminder not found")
    mark_acknowledged(db, reminder_id)
    reminders_acknowledged_total.inc()
    return ReminderAck(acknowledged=True)


