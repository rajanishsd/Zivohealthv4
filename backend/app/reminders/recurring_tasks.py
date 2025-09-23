"""
Tasks for handling recurring reminders
"""
from datetime import datetime, timezone as dt_timezone
from celery import shared_task
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from .unified_service import UnifiedReminderService
from .celery_app import celery_app
from .config import settings
from .metrics import scheduler_scans_total, scheduler_dispatched_total


@shared_task(name="reminders.generate_recurring")
def generate_recurring_occurrences_task() -> int:
    """Generate occurrences for due recurring reminders. Returns number generated."""
    db: Session = SessionLocal()
    generated = 0
    
    try:
        service = UnifiedReminderService(db)
        now = datetime.now(dt_timezone.utc)
        
        # Get due recurring reminders
        print(f"🕒 [Recurrence] generate_recurring_occurrences_task at {now.isoformat()}")
        due_reminders = service.get_due_recurring_reminders(now, limit=settings.SCHEDULER_BATCH_SIZE)
        print(f"🧭 [Recurrence] Due recurring templates: {len(due_reminders)}")
        scheduler_scans_total.inc()
        
        for recurring_reminder in due_reminders:
            try:
                # Generate the occurrence
                print(
                    f"➡️  [Recurrence] Generating occurrence for parent={recurring_reminder.id} "
                    f"last_occ={getattr(recurring_reminder, 'last_occurrence', None)} "
                    f"next_occ={getattr(recurring_reminder, 'next_occurrence', None)}"
                )
                reminder = service.generate_occurrence(recurring_reminder)
                generated += 1
                scheduler_dispatched_total.inc()
                print(
                    f"✅ [Recurrence] Generated child={reminder.id} for parent={recurring_reminder.id}"
                )
                
                # Let scan_and_dispatch handle the generated occurrence
                # No need to publish directly or mark as processed here
                
            except Exception as e:
                print(f"Failed to generate occurrence for recurring reminder {recurring_reminder.id}: {e}")
                
    finally:
        db.close()
    
    return generated


@shared_task(name="reminders.cleanup_expired_recurring")
def cleanup_expired_recurring_task() -> int:
    """Clean up expired recurring reminders. Returns number cleaned up."""
    db: Session = SessionLocal()
    cleaned = 0
    
    try:
        service = UnifiedReminderService(db)
        now = datetime.now(dt_timezone.utc)
        
        # Find reminders that should be deactivated (both single and recurring)
        from .unified_models import Reminder
        from sqlalchemy import select, update
        
        # Reminders past end date (both single and recurring)
        expired_by_date = db.execute(
            select(Reminder)
            .where(Reminder.is_active == True)
            .where(Reminder.end_date <= now)
        ).scalars()
        
        # Reminders that hit max occurrences (both single and recurring)
        expired_by_count = db.execute(
            select(Reminder)
            .where(Reminder.is_active == True)
            .where(Reminder.max_occurrences.isnot(None))
            .where(Reminder.occurrence_count >= Reminder.max_occurrences)
        ).scalars()
        
        # Deactivate expired reminders
        for reminder in list(expired_by_date) + list(expired_by_count):
            if reminder.is_recurring:
                service.deactivate_recurring_reminder(str(reminder.id))
            else:
                # For single-occurrence reminders, just mark as inactive
                db.execute(
                    update(Reminder)
                    .where(Reminder.id == reminder.id)
                    .values(is_active=False)
                )
            cleaned += 1
            
    finally:
        db.close()
    
    return cleaned
