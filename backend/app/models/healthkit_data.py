from datetime import datetime, date
from sqlalchemy import Column, Integer, String, DateTime, Float, Date, Text, ForeignKey, Enum as SQLEnum, Index
from sqlalchemy.orm import relationship
from enum import Enum
from app.db.base import Base

class HealthKitMetricType(str, Enum):
    """Enumeration of supported HealthKit metric types"""
    HEART_RATE = "Heart Rate"
    BLOOD_PRESSURE_SYSTOLIC = "Blood Pressure Systolic"
    BLOOD_PRESSURE_DIASTOLIC = "Blood Pressure Diastolic"
    BLOOD_SUGAR = "Blood Sugar"
    BODY_TEMPERATURE = "Temperature"
    BODY_MASS = "Weight"
    STEP_COUNT = "Steps"
    STAND_TIME = "Stand Hours"
    ACTIVE_ENERGY = "Active Energy"
    FLIGHTS_CLIMBED = "Flights Climbed"
    WORKOUTS = "Workouts"
    SLEEP = "Sleep"
    DISTANCE_WALKING = "Distance Walking"

class TimeGranularity(str, Enum):
    """Time granularity for data aggregation"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

class HealthKitRawData(Base):
    """Raw HealthKit data samples"""
    __tablename__ = "healthkit_raw_data"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    metric_type = Column(SQLEnum(HealthKitMetricType), nullable=False)
    
    # Data fields
    value = Column(Float, nullable=False)
    unit = Column(String, nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    
    # Metadata
    notes = Column(Text)  # For workout types, sleep stages, etc.
    source_device = Column(String)  # Apple Watch, iPhone, etc.
    
    # Tracking
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    # Indexes for efficient querying
    __table_args__ = (
        Index('idx_user_metric_date', 'user_id', 'metric_type', 'start_date'),
        Index('idx_metric_date_range', 'metric_type', 'start_date', 'end_date'),
    )

class HealthKitDailyAggregate(Base):
    """Daily aggregated HealthKit data"""
    __tablename__ = "healthkit_daily_aggregates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    metric_type = Column(SQLEnum(HealthKitMetricType), nullable=False)
    date = Column(Date, nullable=False)
    
    # Aggregated values
    total_value = Column(Float)  # Sum (for steps, calories)
    average_value = Column(Float)  # Average (for heart rate, BP)
    min_value = Column(Float)  # Minimum value
    max_value = Column(Float)  # Maximum value
    count = Column(Integer, default=0)  # Number of samples
    
    # Specific metrics
    duration_minutes = Column(Float)  # For workouts, sleep
    unit = Column(String, nullable=False)
    
    # Metadata
    notes = Column(Text)  # Summary notes
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    # Indexes
    __table_args__ = (
        Index('idx_user_metric_daily', 'user_id', 'metric_type', 'date'),
        Index('idx_date_metric', 'date', 'metric_type'),
    )

class HealthKitWeeklyAggregate(Base):
    """Weekly aggregated HealthKit data"""
    __tablename__ = "healthkit_weekly_aggregates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    metric_type = Column(SQLEnum(HealthKitMetricType), nullable=False)
    week_start_date = Column(Date, nullable=False)  # Monday of the week
    week_end_date = Column(Date, nullable=False)    # Sunday of the week
    
    # Aggregated values
    total_value = Column(Float)
    average_value = Column(Float)
    min_value = Column(Float)
    max_value = Column(Float)
    days_with_data = Column(Integer, default=0)
    
    # Specific metrics
    total_duration_minutes = Column(Float)
    unit = Column(String, nullable=False)
    
    # Metadata
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    # Indexes
    __table_args__ = (
        Index('idx_user_metric_weekly', 'user_id', 'metric_type', 'week_start_date'),
    )

class HealthKitMonthlyAggregate(Base):
    """Monthly aggregated HealthKit data"""
    __tablename__ = "healthkit_monthly_aggregates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    metric_type = Column(SQLEnum(HealthKitMetricType), nullable=False)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)  # 1-12
    
    # Aggregated values
    total_value = Column(Float)
    average_value = Column(Float)
    min_value = Column(Float)
    max_value = Column(Float)
    days_with_data = Column(Integer, default=0)
    
    # Specific metrics
    total_duration_minutes = Column(Float)
    unit = Column(String, nullable=False)
    
    # Metadata
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    # Indexes
    __table_args__ = (
        Index('idx_user_metric_monthly', 'user_id', 'metric_type', 'year', 'month'),
    )

class HealthKitSyncStatus(Base):
    """Track HealthKit sync status for each user"""
    __tablename__ = "healthkit_sync_status"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    
    # Sync tracking
    last_sync_date = Column(DateTime)
    last_successful_sync = Column(DateTime)
    sync_enabled = Column(String, default="true")  # "true", "false", "pending"
    
    # Per-metric last sync dates
    heart_rate_last_sync = Column(DateTime)
    blood_pressure_last_sync = Column(DateTime)
    blood_sugar_last_sync = Column(DateTime)
    temperature_last_sync = Column(DateTime)
    weight_last_sync = Column(DateTime)
    steps_last_sync = Column(DateTime)
    stand_time_last_sync = Column(DateTime)
    active_energy_last_sync = Column(DateTime)
    flights_climbed_last_sync = Column(DateTime)
    workouts_last_sync = Column(DateTime)
    sleep_last_sync = Column(DateTime)
    
    # Error tracking
    last_error = Column(Text)
    error_count = Column(Integer, default=0)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id]) 