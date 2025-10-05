from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, update

from .unified_models import Reminder, DeviceToken
from app.utils.timezone import to_utc_aware
from .unified_schemas import ReminderCreate, DeviceTokenCreate


def create_reminder(db: Session, data: ReminderCreate) -> Reminder:
    # Idempotency: if external_id provided and exists, return existing
    if getattr(data, "external_id", None):
        existing = (
            db.query(Reminder)
            .filter(Reminder.external_id == data.external_id)
            .order_by(Reminder.created_at.desc())
            .first()
        )
        if existing:
            return existing
    # Normalize to UTC-aware for storage in timestamptz column
    normalized_time = to_utc_aware(data.reminder_time)
    
    # Build payload with title and message
    payload = data.payload.copy()
    if data.title:
        payload["title"] = data.title
    if data.message:
        payload["message"] = data.message
    
    reminder = Reminder(
        user_id=data.user_id,
        reminder_type=data.reminder_type,
        reminder_time=normalized_time,
        payload=payload,
        status="Pending",
        external_id=data.external_id,
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    # If no external_id was provided, set it to the generated id so
    # downstream ingestion with external_id can dedupe correctly.
    if reminder.external_id is None:
        reminder.external_id = str(reminder.id)
        db.add(reminder)
        db.commit()
        db.refresh(reminder)
    return reminder


def get_reminder(db: Session, reminder_id: str) -> Optional[Reminder]:
    return db.get(Reminder, reminder_id)


def list_reminders(
    db: Session,
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: int = 100,
) -> List[Reminder]:
    stmt = select(Reminder).order_by(Reminder.reminder_time.desc()).limit(limit)
    if user_id:
        stmt = stmt.where(Reminder.user_id == user_id)
    if status:
        stmt = stmt.where(Reminder.status == status)
    if start:
        stmt = stmt.where(Reminder.reminder_time >= start)
    if end:
        stmt = stmt.where(Reminder.reminder_time <= end)
    return list(db.execute(stmt).scalars())


def mark_processed(db: Session, reminder_id: str) -> None:
    db.execute(
        update(Reminder)
        .where(Reminder.id == reminder_id)
        .values(status="Processed", updated_at=datetime.utcnow())
    )
    db.commit()


def mark_failed(db: Session, reminder_id: str, reason: str) -> None:
    db.execute(
        update(Reminder)
        .where(Reminder.id == reminder_id)
        .values(status="Failed", updated_at=datetime.utcnow())
    )
    db.commit()


def mark_queued(db: Session, reminder_id: str) -> None:
    """Mark a reminder as queued for sending so scans won't pick it up again."""
    db.execute(
        update(Reminder)
        .where(Reminder.id == reminder_id)
        .values(status="Queued", updated_at=datetime.utcnow())
    )
    db.commit()


def mark_skipped(db: Session, reminder_id: str) -> None:
    """Mark a reminder as skipped due to business rules (e.g., already logged)."""
    db.execute(
        update(Reminder)
        .where(Reminder.id == reminder_id)
        .values(status="Skipped", updated_at=datetime.utcnow())
    )
    db.commit()


def mark_acknowledged(db: Session, reminder_id: str) -> None:
    db.execute(
        update(Reminder)
        .where(Reminder.id == reminder_id)
        .values(status="Acknowledged", updated_at=datetime.utcnow())
    )
    db.commit()


def get_due_reminders(db: Session, now: datetime, limit: int = 1000) -> List[Reminder]:
    stmt = (
        select(Reminder)
        .where(Reminder.status == "Pending")
        .where(Reminder.is_recurring == False)  # exclude recurring templates
        .where(Reminder.reminder_time <= now)
        .order_by(Reminder.reminder_time.asc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars())


def upsert_device_token(db: Session, data: DeviceTokenCreate) -> DeviceToken:
    existing = (
        db.query(DeviceToken)
        .filter(DeviceToken.user_id == data.user_id, DeviceToken.platform == data.platform)
        .order_by(DeviceToken.created_at.desc())
        .first()
    )
    if existing:
        existing.fcm_token = data.fcm_token
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing
    token = DeviceToken(user_id=data.user_id, platform=data.platform, fcm_token=data.fcm_token)
    db.add(token)
    db.commit()
    db.refresh(token)
    return token


def get_latest_token_for_user(db: Session, user_id: str, platform: str = "ios") -> Optional[str]:
    t = (
        db.query(DeviceToken)
        .filter(DeviceToken.user_id == user_id, DeviceToken.platform == platform)
        .order_by(DeviceToken.created_at.desc())
        .first()
    )
    return t.fcm_token if t else None


def list_device_tokens(
    db: Session,
    user_id: Optional[str] = None,
    platform: Optional[str] = None,
    limit: int = 100,
) -> List[DeviceToken]:
    """List device tokens with optional filtering."""
    query = db.query(DeviceToken)
    
    if user_id:
        query = query.filter(DeviceToken.user_id == user_id)
    if platform:
        query = query.filter(DeviceToken.platform == platform)
    
    return (
        query
        .order_by(DeviceToken.created_at.desc())
        .limit(limit)
        .all()
    )


