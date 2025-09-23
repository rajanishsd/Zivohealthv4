"""
Unified service for managing both one-time and recurring reminders
"""
from datetime import datetime, timedelta, timezone as dt_timezone
from .unified_models import Reminder
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select, update, and_
from .recurrence_models import RecurrenceCalculator, RecurrencePattern
from .unified_schemas import (
    ReminderCreate, ReminderUpdate, ReminderRead, 
    RecurringReminderCreate, OneTimeReminderCreate
)
from app.utils.timezone import to_utc_aware


class UnifiedReminderService:
    """Unified service for managing all types of reminders"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_reminder(self, data: ReminderCreate) -> Reminder:
        """Create any type of reminder (one-time or recurring)"""
        # Idempotency: if external_id provided and exists, return existing
        if getattr(data, "external_id", None):
            existing = (
                self.db.query(Reminder)
                .filter(Reminder.external_id == data.external_id)
                .first()
            )
            if existing:
                return existing
        if data.recurrence_pattern:
            return self._create_recurring_reminder(data)
        else:
            return self._create_one_time_reminder(data)
    
    def create_one_time_reminder(self, data: OneTimeReminderCreate) -> Reminder:
        """Create a one-time reminder"""
        reminder_time = to_utc_aware(data.reminder_time)
        reminder = Reminder(
            user_id=data.user_id,
            reminder_type=data.reminder_type,
            title=data.title,
            message=data.message,
            payload=data.payload,
            reminder_time=reminder_time,
            status="Pending",
            external_id=data.external_id,
            is_recurring=False,
            is_generated=False,
            # Set limits for single occurrence
            max_occurrences=1,
            end_date=reminder_time + timedelta(minutes=1),  # Slightly after reminder time
            occurrence_count=0,
            is_active=True,
        )
        
        self.db.add(reminder)
        self.db.commit()
        self.db.refresh(reminder)
        
        # Ensure external_id is populated for idempotency if missing
        if not getattr(reminder, "external_id", None):
            reminder.external_id = str(reminder.id)
            self.db.add(reminder)
            self.db.commit()
            self.db.refresh(reminder)

        return reminder
    
    def create_recurring_reminder(self, data: RecurringReminderCreate) -> Reminder:
        """Create a recurring reminder"""
        # Normalize pattern keys (support aliases like 'cron' -> 'cron_expression')
        pattern_dict = self._normalize_recurrence_pattern(data.recurrence_pattern)
        # Calculate first occurrence
        first_occurrence = self._calculate_first_occurrence(
            data.start_date,
            pattern_dict,
        )
        
        reminder = Reminder(
            user_id=data.user_id,
            reminder_type=data.reminder_type,
            title=data.title,
            message=data.message,
            payload=data.payload,
            reminder_time=to_utc_aware(first_occurrence) if first_occurrence else to_utc_aware(data.start_date),
            status="Pending",
            external_id=data.external_id,
            is_recurring=True,
            is_generated=False,
            recurrence_pattern=pattern_dict,
            start_date=to_utc_aware(data.start_date),
            end_date=to_utc_aware(data.end_date) if data.end_date else None,
            max_occurrences=data.max_occurrences,
            timezone=data.timezone,
            next_occurrence=to_utc_aware(first_occurrence) if first_occurrence else to_utc_aware(data.start_date),
            is_active=True,
        )
        
        self.db.add(reminder)
        self.db.commit()
        self.db.refresh(reminder)
        
        # Ensure external_id is populated for idempotency if missing
        if not getattr(reminder, "external_id", None):
            reminder.external_id = str(reminder.id)
            self.db.add(reminder)
            self.db.commit()
            self.db.refresh(reminder)

        return reminder
    
    def update_reminder(self, reminder_id: str, data: ReminderUpdate) -> Optional[Reminder]:
        """Update a reminder"""
        reminder = self.db.get(Reminder, reminder_id)
        if not reminder:
            return None
        
        # Update basic fields
        if data.title is not None:
            reminder.title = data.title
        if data.message is not None:
            reminder.message = data.message
        if data.payload is not None:
            reminder.payload = data.payload
        if data.reminder_time is not None:
            reminder.reminder_time = to_utc_aware(data.reminder_time)
        if data.status is not None:
            reminder.status = data.status
        
        # Update recurrence fields if it's a recurring reminder
        if reminder.is_recurring:
            if data.recurrence_pattern is not None:
                reminder.recurrence_pattern = data.recurrence_pattern
                # Recalculate next occurrence
                reminder.next_occurrence = self._recalculate_next_occurrence(reminder)
            if data.end_date is not None:
                reminder.end_date = to_utc_aware(data.end_date)
            if data.timezone is not None:
                reminder.timezone = data.timezone
            if data.is_active is not None:
                reminder.is_active = data.is_active
        
        reminder.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(reminder)
        
        return reminder
    
    def deactivate_recurring_reminder(self, reminder_id: str) -> bool:
        """Deactivate a recurring reminder"""
        reminder = self.db.get(Reminder, reminder_id)
        if not reminder or not reminder.is_recurring:
            return False
        
        reminder.is_active = False
        reminder.updated_at = datetime.utcnow()
        
        self.db.commit()
        return True
    
    def get_reminder(self, reminder_id: str) -> Optional[Reminder]:
        """Get a reminder by ID"""
        return self.db.get(Reminder, reminder_id)
    
    def list_reminders(
        self,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        is_recurring: Optional[bool] = None,
        is_active: Optional[bool] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Reminder]:
        """List reminders with optional filtering"""
        stmt = select(Reminder).order_by(Reminder.reminder_time.desc()).limit(limit)
        
        if user_id:
            stmt = stmt.where(Reminder.user_id == user_id)
        if status:
            stmt = stmt.where(Reminder.status == status)
        if is_recurring is not None:
            stmt = stmt.where(Reminder.is_recurring == is_recurring)
        if is_active is not None:
            stmt = stmt.where(Reminder.is_active == is_active)
        if start:
            stmt = stmt.where(Reminder.reminder_time >= start)
        if end:
            stmt = stmt.where(Reminder.reminder_time <= end)
        
        return list(self.db.execute(stmt).scalars())
    
    def get_due_reminders(self, now: datetime, limit: int = 1000) -> List[Reminder]:
        """Get reminders that are due for processing"""
        stmt = (
            select(Reminder)
            .where(Reminder.status == "Pending")
            .where(Reminder.reminder_time <= now)
            .order_by(Reminder.reminder_time.asc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars())
    
    def get_due_recurring_reminders(self, now: datetime, limit: int = 1000) -> List[Reminder]:
        """Get recurring reminders that are due for generating occurrences"""
        stmt = (
            select(Reminder)
            .where(Reminder.is_recurring == True)
            .where(Reminder.is_active == True)
            .where(Reminder.next_occurrence <= now)
            .where(
                (Reminder.end_date.is_(None)) | 
                (Reminder.end_date > now)
            )
            .where(
                (Reminder.max_occurrences.is_(None)) |
                (Reminder.occurrence_count < Reminder.max_occurrences)
            )
            .order_by(Reminder.next_occurrence.asc())
            .limit(limit)
        )
        
        return list(self.db.execute(stmt).scalars())
    
    def generate_occurrence(self, recurring_reminder: Reminder) -> Reminder:
        """Generate a single occurrence of a recurring reminder"""
        # Create the occurrence
        occurrence = Reminder(
            user_id=recurring_reminder.user_id,
            reminder_type=recurring_reminder.reminder_type,
            title=recurring_reminder.title,
            message=recurring_reminder.message,
            payload=recurring_reminder.payload.copy(),
            reminder_time=recurring_reminder.next_occurrence,
            status="Pending",
            external_id=f"{recurring_reminder.external_id}_{recurring_reminder.occurrence_count + 1}" if recurring_reminder.external_id else None,
            is_recurring=False,  # Occurrences are not recurring themselves
            parent_reminder_id=recurring_reminder.id,
            occurrence_number=recurring_reminder.occurrence_count + 1,
            is_generated=True,
        )
        
        self.db.add(occurrence)
        
        # Update the recurring reminder
        from app.utils.timezone import to_utc_aware as _to_utc
        recurring_reminder.last_occurrence = _to_utc(recurring_reminder.next_occurrence)
        recurring_reminder.occurrence_count += 1
        
        # Calculate next occurrence
        print(
            f"🧮 [Recurrence] Calc next for parent={recurring_reminder.id} "
            f"occ_count={recurring_reminder.occurrence_count} "
            f"last_occ={getattr(recurring_reminder, 'last_occurrence', None)}"
        )
        next_occurrence = self._calculate_next_occurrence(recurring_reminder)
        print(f"🧮 [Recurrence] Next occurrence computed: {next_occurrence}")
        recurring_reminder.next_occurrence = _to_utc(next_occurrence) if next_occurrence else None
        
        # Only mark as completed when max occurrences reached
        max_reached = (
            recurring_reminder.max_occurrences is not None and
            recurring_reminder.occurrence_count >= recurring_reminder.max_occurrences
        )
        if max_reached:
            recurring_reminder.is_active = False
            recurring_reminder.next_occurrence = None
            recurring_reminder.status = "Processed"
        else:
            # Keep template active for further occurrences
            recurring_reminder.is_active = True
        
        recurring_reminder.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(occurrence)
        
        return occurrence
    
    def mark_processed(self, reminder_id: str) -> None:
        """Mark a reminder as processed"""
        self.db.execute(
            update(Reminder)
            .where(Reminder.id == reminder_id)
            .values(status="Processed", updated_at=datetime.utcnow())
        )
        self.db.commit()
    
    def mark_acknowledged(self, reminder_id: str) -> None:
        """Mark a reminder as acknowledged"""
        self.db.execute(
            update(Reminder)
            .where(Reminder.id == reminder_id)
            .values(status="Acknowledged", updated_at=datetime.utcnow())
        )
        self.db.commit()
    
    def mark_failed(self, reminder_id: str, reason: str) -> None:
        """Mark a reminder as failed"""
        self.db.execute(
            update(Reminder)
            .where(Reminder.id == reminder_id)
            .values(status="Failed", updated_at=datetime.utcnow())
        )
        self.db.commit()
    
    def get_reminder_stats(self, user_id: Optional[str] = None) -> Dict[str, int]:
        """Get reminder statistics"""
        base_query = select(Reminder)
        if user_id:
            base_query = base_query.where(Reminder.user_id == user_id)
        
        total = len(list(self.db.execute(base_query).scalars()))
        one_time = len(list(self.db.execute(base_query.where(Reminder.is_recurring == False)).scalars()))
        recurring = len(list(self.db.execute(base_query.where(Reminder.is_recurring == True)).scalars()))
        active_recurring = len(list(self.db.execute(base_query.where(and_(Reminder.is_recurring == True, Reminder.is_active == True))).scalars()))
        pending = len(list(self.db.execute(base_query.where(Reminder.status == "Pending")).scalars()))
        processed = len(list(self.db.execute(base_query.where(Reminder.status == "Processed")).scalars()))
        
        return {
            "total_reminders": total,
            "one_time_reminders": one_time,
            "recurring_reminders": recurring,
            "active_recurring": active_recurring,
            "pending_reminders": pending,
            "processed_reminders": processed,
        }
    
    def _create_one_time_reminder(self, data: ReminderCreate) -> Reminder:
        """Create a one-time reminder from unified data"""
        return self.create_one_time_reminder(OneTimeReminderCreate(
            user_id=data.user_id,
            reminder_type=data.reminder_type,
            title=data.title,
            message=data.message,
            payload=data.payload,
            reminder_time=data.reminder_time,
            external_id=data.external_id,
        ))
    
    def _create_recurring_reminder(self, data: ReminderCreate) -> Reminder:
        """Create a recurring reminder from unified data"""
        return self.create_recurring_reminder(RecurringReminderCreate(
            user_id=data.user_id,
            reminder_type=data.reminder_type,
            title=data.title,
            message=data.message,
            payload=data.payload,
            recurrence_pattern=data.recurrence_pattern,
            start_date=data.start_date or data.reminder_time,
            end_date=data.end_date,
            max_occurrences=data.max_occurrences,
            timezone=data.timezone,
            external_id=data.external_id,
        ))
    
    def _calculate_first_occurrence(self, start_date: datetime, pattern_dict: Dict[str, Any]) -> Optional[datetime]:
        """Calculate the first occurrence based on pattern"""
        # For now, return start_date - in production, this would be more sophisticated
        return start_date
    
    def _calculate_next_occurrence(self, recurring_reminder: Reminder) -> Optional[datetime]:
        """Calculate the next occurrence for a recurring reminder"""
        # Use last_occurrence as base, or start_date if no previous occurrence
        base_time = recurring_reminder.last_occurrence or recurring_reminder.start_date
        if not base_time:
            return None
        
        # Parse the recurrence pattern
        pattern = self._parse_recurrence_pattern(recurring_reminder.recurrence_pattern)
        
        # Use the calculator to get next occurrence
        return RecurrenceCalculator.calculate_next_occurrence(
            pattern,
            base_time,
            datetime.now(dt_timezone.utc)
        )
    
    def _recalculate_next_occurrence(self, recurring_reminder: Reminder) -> Optional[datetime]:
        """Recalculate next occurrence after pattern change"""
        if recurring_reminder.last_occurrence:
            base_time = recurring_reminder.last_occurrence
        else:
            base_time = recurring_reminder.start_date
        
        pattern = self._parse_recurrence_pattern(recurring_reminder.recurrence_pattern)
        return RecurrenceCalculator.calculate_next_occurrence(
            pattern,
            base_time,
            datetime.utcnow()
        )
    
    def _parse_recurrence_pattern(self, pattern_dict: Dict[str, Any]):
        """Parse stored pattern dict back into the correct pattern class"""
        from .recurrence_models import (
            RecurrenceType,
            RecurrencePattern as BasePattern,
            WeeklyPattern,
            MonthlyPattern,
            CustomPattern,
        )

        # Normalize keys before parsing (accept 'cron' alias)
        pattern_dict = self._normalize_recurrence_pattern(pattern_dict)
        recurrence_type = RecurrenceType(pattern_dict["type"])

        if recurrence_type == RecurrenceType.CUSTOM:
            return CustomPattern.from_dict(pattern_dict)
        if recurrence_type == RecurrenceType.WEEKLY:
            return WeeklyPattern.from_dict(pattern_dict)
        if recurrence_type == RecurrenceType.MONTHLY:
            return MonthlyPattern.from_dict(pattern_dict)

        # Fallback for simple patterns (daily/quarterly/yearly)
        return BasePattern.from_dict(pattern_dict)

    def _normalize_recurrence_pattern(self, pattern_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize incoming recurrence pattern keys to expected schema.
        - Accept 'cron' as alias for 'cron_expression'.
        """
        if not pattern_dict:
            return pattern_dict
        normalized = dict(pattern_dict)
        if normalized.get("type") == "custom":
            if "cron_expression" not in normalized and "cron" in normalized:
                normalized["cron_expression"] = normalized["cron"]
        return normalized
