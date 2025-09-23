"""
Unified reminder models - single table for both one-time and recurring reminders
"""
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

from app.db.base import Base


class Reminder(Base):
    """Unified reminder model - handles both one-time and recurring reminders"""
    __tablename__ = "reminders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, nullable=False, index=True)
    reminder_type = Column(String, nullable=False)
    title = Column(String, nullable=True)
    message = Column(String, nullable=True)
    payload = Column(JSONB, nullable=False, default=dict)
    reminder_time = Column(DateTime(timezone=True), nullable=False, index=True)
    status = Column(String, nullable=False, default="Pending")
    external_id = Column(String, nullable=True, index=True)
    
    # Recurrence fields (NULL for one-time reminders)
    recurrence_pattern = Column(JSONB, nullable=True)  # Stores recurrence pattern as JSON
    is_recurring = Column(Boolean, nullable=False, default=False)
    parent_reminder_id = Column(UUID(as_uuid=True), nullable=True)  # For generated occurrences
    occurrence_number = Column(Integer, nullable=True)  # Which occurrence this is
    is_generated = Column(Boolean, nullable=False, default=False)  # True for generated occurrences
    
    # Recurrence management fields
    start_date = Column(DateTime(timezone=True), nullable=True)  # When recurrence starts
    end_date = Column(DateTime(timezone=True), nullable=True)  # When recurrence ends
    max_occurrences = Column(Integer, nullable=True)  # Max number of occurrences
    timezone = Column(String, nullable=True)  # User timezone for recurrence
    last_occurrence = Column(DateTime(timezone=True), nullable=True)  # Last generated occurrence
    next_occurrence = Column(DateTime(timezone=True), nullable=True, index=True)  # Next occurrence time
    occurrence_count = Column(Integer, nullable=False, default=0)  # How many occurrences generated
    is_active = Column(Boolean, nullable=False, default=True)  # Whether recurrence is active
    
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_reminders_status_time", "status", "reminder_time"),
        Index("ix_reminders_user_time", "user_id", "reminder_time"),
        Index("ix_reminders_recurring_active", "is_recurring", "is_active"),
        Index("ix_reminders_next_occurrence", "next_occurrence"),
        Index("ix_reminders_parent_id", "parent_reminder_id"),
    )


class DeviceToken(Base):
    """Device token model (unchanged)"""
    __tablename__ = "device_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, nullable=False, index=True)
    platform = Column(String, nullable=False, index=True)  # ios, android, web
    fcm_token = Column(String, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_device_tokens_user_platform", "user_id", "platform"),
    )
