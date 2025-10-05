from datetime import datetime, timezone as dt_timezone
from celery import shared_task
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.session import SessionLocal
from .repository import create_reminder, get_due_reminders, mark_processed, mark_failed, mark_queued, mark_skipped
from .unified_schemas import ReminderCreate
from .celery_app import celery_app
from .config import settings
from .dispatcher import send_push_via_fcm
from .metrics import scheduler_scans_total, scheduler_dispatched_total
from app.models.nutrition_data import NutritionRawData
from app.utils.timezone import get_zoneinfo
from sqlalchemy import text as _sa_text
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore


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
                # Conditional skip: if nutrition log already recorded for the same day and meal
                if _should_skip_nutrition_log(db, r):
                    # Mark as skipped for observability (not processed)
                    print(f"🔍 [Reminders] Skipping nutrition log for user {r.user_id} and meal {r.payload.get('meal')}")
                    mark_skipped(db, r.id)
                    continue
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
                # Mark as queued; dispatch task will mark Processed/Failed
                mark_queued(db, r.id)
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
def _should_skip_nutrition_log(db: Session, reminder) -> bool:
    """
    For reminders of type "nutrition_log", check if the user has already logged
    the corresponding meal on the same local day as the reminder time.
    If yes, return True to skip dispatching this reminder.
    """
    try:
        if getattr(reminder, "reminder_type", "") != "nutrition_log":
            return False

        payload = getattr(reminder, "payload", {}) or {}
        # Preferred order: explicit meal, then context.key
        meal_key = (payload.get("meal") or payload.get("context", {}).get("key") or "").strip().lower()
        if not meal_key:
            return False

        # Convert user_id to int for NutritionRawData lookup
        try:
            user_id_int = int(str(reminder.user_id))
        except Exception:
            return False

        # Determine local date for comparison using reminder timezone if present,
        # otherwise fallback to user's profile timezone, then DEFAULT_TIMEZONE
        tz = None
        tz_name = getattr(reminder, "timezone", None)
        if tz_name and ZoneInfo is not None:
            try:
                tz = ZoneInfo(tz_name)
            except Exception:
                tz = None
        if tz is None:
            # Try user profile timezone from DB
            try:
                row = db.execute(
                    _sa_text("SELECT timezone FROM user_profiles WHERE user_id = :uid"),
                    {"uid": int(str(reminder.user_id))},
                ).first()
                if row and row[0] and ZoneInfo is not None:
                    try:
                        tz = ZoneInfo(str(row[0]))
                    except Exception:
                        tz = None
            except Exception:
                tz = None
            if tz is None:
                tz = get_zoneinfo()

        rt = reminder.reminder_time
        try:
            if tz is not None:
                local_date = (rt if rt.tzinfo else rt.replace(tzinfo=dt_timezone.utc)).astimezone(tz).date()
            else:
                # Fallback: use UTC date
                local_date = (rt if rt.tzinfo else rt.replace(tzinfo=dt_timezone.utc)).astimezone(dt_timezone.utc).date()
        except Exception:
            # On any conversion issue, do not skip
            return False

        count_ = (
            db.query(func.count(NutritionRawData.id))
            .filter(
                NutritionRawData.user_id == user_id_int,
                NutritionRawData.meal_date == local_date,
                NutritionRawData.meal_type == meal_key,
            )
            .scalar()
        )
        should_skip = bool(count_ and count_ >= 1)
        # Debug trace to help diagnose timezone-related skipping
        try:
            print(
                f"🔎 [Reminders] Skip check | user={reminder.user_id} meal={meal_key} tz={(tz.key if hasattr(tz,'key') else str(tz))} "
                f"rt_utc={(rt if rt.tzinfo else rt.replace(tzinfo=dt_timezone.utc)).astimezone(dt_timezone.utc).isoformat()} "
                f"local_date={local_date} count={count_} skip={should_skip}"
            )
        except Exception:
            pass
        return should_skip
    except Exception:
        # Fail-safe: never block sending due to unexpected errors
        return False



