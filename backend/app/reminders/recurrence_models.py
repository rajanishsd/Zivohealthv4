"""
Recurring reminder models and patterns
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum
from dataclasses import dataclass
import json
import re
from croniter import croniter


class RecurrenceType(Enum):
    """Types of recurrence patterns"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    CUSTOM = "custom"


class Weekday(Enum):
    """Days of the week"""
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6


@dataclass
class RecurrencePattern:
    """Base recurrence pattern"""
    type: RecurrenceType
    interval: int = 1  # Every N days/weeks/months/years
    end_date: Optional[datetime] = None
    max_occurrences: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "interval": self.interval,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "max_occurrences": self.max_occurrences
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RecurrencePattern':
        return cls(
            type=RecurrenceType(data["type"]),
            interval=data.get("interval", 1),
            end_date=datetime.fromisoformat(data["end_date"]) if data.get("end_date") else None,
            max_occurrences=data.get("max_occurrences")
        )


@dataclass
class WeeklyPattern(RecurrencePattern):
    """Weekly recurrence with specific days"""
    weekdays: List[Weekday] = None  # e.g., [MONDAY, WEDNESDAY, FRIDAY]
    
    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base["weekdays"] = [day.value for day in self.weekdays] if self.weekdays else []
        return base
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WeeklyPattern':
        return cls(
            type=RecurrenceType(data["type"]),
            interval=data.get("interval", 1),
            end_date=datetime.fromisoformat(data["end_date"]) if data.get("end_date") else None,
            max_occurrences=data.get("max_occurrences"),
            weekdays=[Weekday(day) for day in data.get("weekdays", [])]
        )


@dataclass
class MonthlyPattern(RecurrencePattern):
    """Monthly recurrence with specific day of month"""
    day_of_month: int = 1  # 1-31, or -1 for last day of month
    
    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base["day_of_month"] = self.day_of_month
        return base
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MonthlyPattern':
        return cls(
            type=RecurrenceType(data["type"]),
            interval=data.get("interval", 1),
            end_date=datetime.fromisoformat(data["end_date"]) if data.get("end_date") else None,
            max_occurrences=data.get("max_occurrences"),
            day_of_month=data["day_of_month"]
        )


@dataclass
class CustomPattern(RecurrencePattern):
    """Custom recurrence using cron-like expressions"""
    cron_expression: str = ""  # e.g., "0 9 * * 1,3,5" (9 AM Mon, Wed, Fri)
    
    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base["cron_expression"] = self.cron_expression
        return base
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CustomPattern':
        return cls(
            type=RecurrenceType(data["type"]),
            interval=data.get("interval", 1),
            end_date=datetime.fromisoformat(data["end_date"]) if data.get("end_date") else None,
            max_occurrences=data.get("max_occurrences"),
            cron_expression=data["cron_expression"]
        )


class RecurrenceCalculator:
    """Calculates next occurrence for recurrence patterns"""
    
    @staticmethod
    def calculate_next_occurrence(
        pattern: RecurrencePattern, 
        last_occurrence: datetime,
        current_time: Optional[datetime] = None
    ) -> Optional[datetime]:
        """Calculate next occurrence based on pattern"""
        if current_time is None:
            current_time = datetime.utcnow()
        
        if isinstance(pattern, WeeklyPattern):
            return RecurrenceCalculator._calculate_weekly_next(
                pattern, last_occurrence, current_time
            )
        elif isinstance(pattern, MonthlyPattern):
            return RecurrenceCalculator._calculate_monthly_next(
                pattern, last_occurrence, current_time
            )
        elif isinstance(pattern, CustomPattern):
            return RecurrenceCalculator._calculate_cron_next(
                pattern, last_occurrence, current_time
            )
        else:
            return RecurrenceCalculator._calculate_simple_next(
                pattern, last_occurrence, current_time
            )
    
    @staticmethod
    def _calculate_weekly_next(
        pattern: WeeklyPattern, 
        last_occurrence: datetime, 
        current_time: datetime
    ) -> Optional[datetime]:
        """Calculate next weekly occurrence"""
        # Find next occurrence within the week
        for day_offset in range(7):
            candidate = last_occurrence + timedelta(days=day_offset)
            if candidate.weekday() in [d.value for d in pattern.weekdays]:
                if candidate > current_time:
                    return candidate
        
        # If not found in current week, move to next interval
        next_week = last_occurrence + timedelta(weeks=pattern.interval)
        for day_offset in range(7):
            candidate = next_week + timedelta(days=day_offset)
            if candidate.weekday() in [d.value for d in pattern.weekdays]:
                return candidate
        
        return None
    
    @staticmethod
    def _calculate_monthly_next(
        pattern: MonthlyPattern, 
        last_occurrence: datetime, 
        current_time: datetime
    ) -> Optional[datetime]:
        """Calculate next monthly occurrence"""
        # Move to next month
        if last_occurrence.month == 12:
            next_month = last_occurrence.replace(year=last_occurrence.year + 1, month=1)
        else:
            next_month = last_occurrence.replace(month=last_occurrence.month + pattern.interval)
        
        # Handle day of month
        if pattern.day_of_month == -1:  # Last day of month
            # Get last day of the month
            if next_month.month == 12:
                next_month = next_month.replace(year=next_month.year + 1, month=1)
            else:
                next_month = next_month.replace(month=next_month.month + 1)
            next_month = next_month.replace(day=1) - timedelta(days=1)
        else:
            # Ensure day exists in the month
            try:
                next_month = next_month.replace(day=pattern.day_of_month)
            except ValueError:
                # Day doesn't exist in month, use last day
                if next_month.month == 12:
                    next_month = next_month.replace(year=next_month.year + 1, month=1)
                else:
                    next_month = next_month.replace(month=next_month.month + 1)
                next_month = next_month.replace(day=1) - timedelta(days=1)
        
        return next_month if next_month > current_time else None
    
    @staticmethod
    def _calculate_cron_next(
        pattern: CustomPattern, 
        last_occurrence: datetime, 
        current_time: datetime
    ) -> Optional[datetime]:
        """Calculate next occurrence for cron expression using croniter."""
        try:
            base = max(last_occurrence, current_time)
            print(f"🧭 [Cron] base={base.isoformat()} expr={pattern.cron_expression}")
            itr = croniter(pattern.cron_expression, base)
            nxt = itr.get_next(datetime)
            print(f"🧭 [Cron] next={nxt.isoformat()}")
            return nxt
        except Exception:
            print("❌ [Cron] Failed to compute next with croniter")
            return None
    
    @staticmethod
    def _calculate_simple_next(
        pattern: RecurrencePattern, 
        last_occurrence: datetime, 
        current_time: datetime
    ) -> Optional[datetime]:
        """Calculate next occurrence for simple patterns"""
        if pattern.type == RecurrenceType.DAILY:
            return last_occurrence + timedelta(days=pattern.interval)
        elif pattern.type == RecurrenceType.QUARTERLY:
            return last_occurrence + timedelta(days=90 * pattern.interval)
        elif pattern.type == RecurrenceType.YEARLY:
            return last_occurrence + timedelta(days=365 * pattern.interval)
        
        return None


# Predefined patterns for common use cases
class CommonPatterns:
    """Common recurrence patterns"""
    
    @staticmethod
    def daily() -> RecurrencePattern:
        return RecurrencePattern(type=RecurrenceType.DAILY, interval=1)
    
    @staticmethod
    def weekdays() -> WeeklyPattern:
        return WeeklyPattern(
            type=RecurrenceType.WEEKLY,
            interval=1,
            weekdays=[Weekday.MONDAY, Weekday.TUESDAY, Weekday.WEDNESDAY, 
                     Weekday.THURSDAY, Weekday.FRIDAY]
        )
    
    @staticmethod
    def weekends() -> WeeklyPattern:
        return WeeklyPattern(
            type=RecurrenceType.WEEKLY,
            interval=1,
            weekdays=[Weekday.SATURDAY, Weekday.SUNDAY]
        )
    
    @staticmethod
    def weekly(weekdays: List[Weekday]) -> WeeklyPattern:
        return WeeklyPattern(
            type=RecurrenceType.WEEKLY,
            interval=1,
            weekdays=weekdays
        )
    
    @staticmethod
    def biweekly(weekdays: List[Weekday]) -> WeeklyPattern:
        return WeeklyPattern(
            type=RecurrenceType.WEEKLY,
            interval=2,
            weekdays=weekdays
        )
    
    @staticmethod
    def monthly(day_of_month: int) -> MonthlyPattern:
        return MonthlyPattern(
            type=RecurrenceType.MONTHLY,
            interval=1,
            day_of_month=day_of_month
        )
    
    @staticmethod
    def quarterly() -> RecurrencePattern:
        return RecurrencePattern(type=RecurrenceType.QUARTERLY, interval=1)
    
    @staticmethod
    def yearly() -> RecurrencePattern:
        return RecurrencePattern(type=RecurrenceType.YEARLY, interval=1)
