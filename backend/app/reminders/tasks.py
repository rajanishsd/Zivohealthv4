from datetime import datetime, timezone as dt_timezone
from celery import shared_task
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from .repository import create_reminder, get_due_reminders, mark_processed, mark_failed
from .unified_schemas import ReminderCreate
from .celery_app import celery_app
from .config import settings
from .dispatcher import send_push_via_fcm
from .metrics import scheduler_scans_total, scheduler_dispatched_total


@shared_task(name="reminders.ingest")
def ingest_reminder_task(event: dict) -> None:
    db: Session = SessionLocal()
    try:
        data = ReminderCreate(**event)
        # Use unified service so recurrence and idempotency are handled centrally
        from .unified_service import UnifiedReminderService
        UnifiedReminderService(db).create_reminder(data)
    except Exception:
        # Ingest errors can be monitored; we don't re-raise to avoid retry storms yet
        pass
    finally:
        db.close()


@shared_task(name="reminders.scan_and_dispatch")
def scan_and_dispatch_task() -> int:
    """Scan for due reminders and publish to output queue. Returns number dispatched."""
    db: Session = SessionLocal()
    dispatched = 0
    try:
        # Use timezone-aware UTC to compare with timestamptz column
        now = datetime.now(dt_timezone.utc)
        due = get_due_reminders(db, now, limit=settings.SCHEDULER_BATCH_SIZE)
        scheduler_scans_total.inc()
        for r in due:
            try:
                # Only include title/message if they are not None to avoid overriding
                # pre-populated payload values with nulls
                payload_payload = {**r.payload}
                if r.title is not None:
                    payload_payload["title"] = r.title
                if r.message is not None:
                    payload_payload["message"] = r.message

                payload = {
                    "user_id": r.user_id,
                    "reminder_id": str(r.id),
                    "reminder_type": r.reminder_type,
                    "payload": payload_payload,
                    "timestamp": r.reminder_time.isoformat(),
                }
                celery_app.send_task(
                    "reminders.dispatch",
                    args=[payload],
                    queue=settings.RABBITMQ_OUTPUT_QUEUE,
                    routing_key=settings.RABBITMQ_OUTPUT_ROUTING_KEY,
                )
                mark_processed(db, r.id)
                dispatched += 1
                scheduler_dispatched_total.inc()
            except Exception:
                mark_failed(db, r.id, reason="publish_failed")
    finally:
        db.close()
    return dispatched


@shared_task(name="reminders.dispatch")
def dispatch_task(output_event: dict) -> None:
    """Consume output queue and send push via FCM."""
    send_push_via_fcm(output_event)
    return None


