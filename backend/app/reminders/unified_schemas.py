"""
Unified schemas for both one-time and recurring reminders
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, Literal
from pydantic import BaseModel, Field
from enum import Enum

from .recurrence_models import RecurrenceType, Weekday


# Status and basic schemas
ReminderStatus = Literal["Pending", "Processed", "Acknowledged", "Failed"]


class ReminderAck(BaseModel):
    """Schema for acknowledging reminders"""
    acknowledged: bool = True


class ReminderQueued(BaseModel):
    """Schema returned when a reminder is enqueued for creation"""
    external_id: str
    queued_at: datetime


class DeviceTokenCreate(BaseModel):
    """Schema for creating device tokens"""
    user_id: str
    platform: str = Field(..., pattern="^(ios|android|web)$")
    fcm_token: str


class DeviceTokenRead(BaseModel):
    """Schema for reading device tokens"""
    id: str
    user_id: str
    platform: str
    fcm_token: str
    created_at: datetime
    updated_at: datetime


class ReminderCreate(BaseModel):
    """Schema for creating any type of reminder"""
    user_id: str
    reminder_type: str
    title: Optional[str] = None
    message: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    reminder_time: datetime
    external_id: Optional[str] = None
    
    # Recurrence fields (optional - if not provided, creates one-time reminder)
    recurrence_pattern: Optional[Dict[str, Any]] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    max_occurrences: Optional[int] = Field(default=None, ge=1)
    timezone: Optional[str] = None


class ReminderRead(BaseModel):
    """Schema for reading any type of reminder"""
    id: str
    user_id: str
    reminder_type: str
    title: Optional[str]
    message: Optional[str]
    payload: Dict[str, Any]
    reminder_time: datetime
    status: str
    external_id: Optional[str]
    
    # Recurrence fields
    is_recurring: bool
    recurrence_pattern: Optional[Dict[str, Any]] = None
    parent_reminder_id: Optional[str] = None
    occurrence_number: Optional[int] = None
    is_generated: bool
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    max_occurrences: Optional[int] = None
    timezone: Optional[str] = None
    last_occurrence: Optional[datetime] = None
    next_occurrence: Optional[datetime] = None
    occurrence_count: int
    is_active: bool
    
    created_at: datetime
    updated_at: datetime


class ReminderUpdate(BaseModel):
    """Schema for updating reminders"""
    title: Optional[str] = None
    message: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    reminder_time: Optional[datetime] = None
    status: Optional[str] = None
    
    # Recurrence fields
    recurrence_pattern: Optional[Dict[str, Any]] = None
    end_date: Optional[datetime] = None
    timezone: Optional[str] = None
    is_active: Optional[bool] = None


class RecurringReminderCreate(BaseModel):
    """Schema specifically for creating recurring reminders"""
    user_id: str
    reminder_type: str
    title: Optional[str] = None
    message: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    recurrence_pattern: Dict[str, Any]  # Required for recurring
    start_date: datetime  # Required for recurring
    end_date: Optional[datetime] = None
    max_occurrences: Optional[int] = Field(default=None, ge=1)
    timezone: Optional[str] = None
    external_id: Optional[str] = None


class OneTimeReminderCreate(BaseModel):
    """Schema specifically for creating one-time reminders"""
    user_id: str
    reminder_type: str
    title: Optional[str] = None
    message: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    reminder_time: datetime  # Required for one-time
    external_id: Optional[str] = None


class ReminderStats(BaseModel):
    """Schema for reminder statistics"""
    total_reminders: int
    one_time_reminders: int
    recurring_reminders: int
    active_recurring: int
    pending_reminders: int
    processed_reminders: int


# Predefined pattern schemas for common use cases
class DailyPattern(BaseModel):
    """Daily recurrence pattern"""
    type: str = "daily"
    interval: int = Field(default=1, ge=1)
    end_date: Optional[datetime] = None
    max_occurrences: Optional[int] = None


class WeeklyPattern(BaseModel):
    """Weekly recurrence pattern"""
    type: str = "weekly"
    interval: int = Field(default=1, ge=1)
    weekdays: List[int] = Field(..., description="List of weekday numbers (0=Monday, 6=Sunday)")
    end_date: Optional[datetime] = None
    max_occurrences: Optional[int] = None


class MonthlyPattern(BaseModel):
    """Monthly recurrence pattern"""
    type: str = "monthly"
    interval: int = Field(default=1, ge=1)
    day_of_month: int = Field(..., ge=1, le=31)
    end_date: Optional[datetime] = None
    max_occurrences: Optional[int] = None


class QuarterlyPattern(BaseModel):
    """Quarterly recurrence pattern"""
    type: str = "quarterly"
    interval: int = Field(default=1, ge=1)
    end_date: Optional[datetime] = None
    max_occurrences: Optional[int] = None


class YearlyPattern(BaseModel):
    """Yearly recurrence pattern"""
    type: str = "yearly"
    interval: int = Field(default=1, ge=1)
    end_date: Optional[datetime] = None
    max_occurrences: Optional[int] = None


class CustomPattern(BaseModel):
    """Custom cron pattern"""
    type: str = "custom"
    cron_expression: str = Field(..., pattern=r'^(\*|[0-5]?\d) (\*|[01]?\d|2[0-3]) (\*|[12]?\d|3[01]) (\*|[1-9]|1[0-2]) (\*|[0-6])$')
    end_date: Optional[datetime] = None
    max_occurrences: Optional[int] = None
