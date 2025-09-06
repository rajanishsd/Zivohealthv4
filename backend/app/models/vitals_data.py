from datetime import datetime, date
from sqlalchemy import Column, Integer, String, DateTime, Float, Date, Text, ForeignKey, Enum as SQLEnum, Index, UniqueConstraint, text
from sqlalchemy.orm import relationship
from enum import Enum
from app.db.base import Base
from app.utils.timezone import local_now_db_expr, local_now_db_func

class VitalMetricType(str, Enum):
    """Enumeration of supported vital metric types"""
    HEART_RATE = "Heart Rate"
    BLOOD_PRESSURE_SYSTOLIC = "Blood Pressure Systolic"
    BLOOD_PRESSURE_DIASTOLIC = "Blood Pressure Diastolic"
    BLOOD_SUGAR = "Blood Sugar"
    BODY_TEMPERATURE = "Temperature"
    BODY_MASS = "Weight"
    HEIGHT = "Height"
    BMI = "BMI"
    OXYGEN_SATURATION = "Oxygen Saturation"
    STEP_COUNT = "Steps"
    STAND_TIME = "Stand Hours"
    ACTIVE_ENERGY = "Active Energy"
    FLIGHTS_CLIMBED = "Flights Climbed"
    WORKOUTS = "Workouts"
    WORKOUT_DURATION = "Workout Duration"
    WORKOUT_CALORIES = "Workout Calories"
    WORKOUT_DISTANCE = "Workout Distance"
    SLEEP = "Sleep"
    DISTANCE_WALKING = "Distance Walking"

class VitalDataSource(str, Enum):
    """Source of vital data"""
    APPLE_HEALTHKIT = "apple_healthkit"
    MANUAL_ENTRY = "manual_entry"
    DOCUMENT_EXTRACTION = "document_extraction"
    DEVICE_SYNC = "device_sync"
    API_IMPORT = "api_import"

class TimeGranularity(str, Enum):
    """Time granularity for data aggregation"""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

class VitalsRawData(Base):
    """Raw vitals data from all sources"""
    __tablename__ = "vitals_raw_data"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    metric_type = Column(String, nullable=False)  # Store as string to match enum values
    
    # Data fields
    value = Column(Float, nullable=False)
    unit = Column(String, nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    
    # Source tracking
    data_source = Column(String, nullable=False)  # Store as string to match enum values
    source_device = Column(String)  # Apple Watch, iPhone, Blood Pressure Monitor, etc.
    
    # Metadata
    notes = Column(Text)  # For workout types, sleep stages, etc.
    confidence_score = Column(Float)  # OCR/extraction confidence for document sources
    
    # Aggregation tracking
    aggregation_status = Column(String(20), nullable=False, default='pending')  # pending, processing, completed, failed
    aggregated_at = Column(DateTime, nullable=True)  # When aggregation was completed
    
    # Tracking
    created_at = Column(DateTime, server_default=local_now_db_expr())
    updated_at = Column(DateTime, server_default=local_now_db_expr(), onupdate=local_now_db_func())
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    # Indexes for efficient querying
    __table_args__ = (
        Index('idx_user_metric_date', 'user_id', 'metric_type', 'start_date'),
        Index('idx_metric_date_range', 'metric_type', 'start_date', 'end_date'),
        Index('idx_user_source_date', 'user_id', 'data_source', 'start_date'),
        Index('idx_aggregation_status', 'aggregation_status', 'user_id', 'start_date'),
        # Functional unique index that treats NULL notes as empty string to prevent duplicates
        Index('ux_vitals_raw_data_nodups', 'user_id', 'metric_type', 'unit', 'start_date', 'data_source', 
              text("COALESCE(notes, '')"), unique=True),
    )

class VitalsRawCategorized(Base):
    """Categorized vitals data with LOINC codes"""
    __tablename__ = "vitals_raw_categorized"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    metric_type = Column(String, nullable=False)  # Store as string to match enum values
    
    # Data fields
    value = Column(Float, nullable=False)
    unit = Column(String, nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    
    # Source tracking
    data_source = Column(String, nullable=False)  # Store as string to match enum values
    source_device = Column(String)  # Apple Watch, iPhone, Blood Pressure Monitor, etc.
    
    # LOINC code for standardized vital sign identification
    loinc_code = Column(String(20), nullable=True, index=True)
    
    # Metadata
    notes = Column(Text)  # For workout types, sleep stages, etc.
    confidence_score = Column(Float)  # OCR/extraction confidence for document sources
    
    # Aggregation tracking
    aggregation_status = Column(String(20), nullable=False, default='pending')  # pending, processing, completed, failed
    aggregated_at = Column(DateTime, nullable=True)  # When aggregation was completed
    
    # Tracking
    created_at = Column(DateTime, server_default=local_now_db_expr())
    updated_at = Column(DateTime, server_default=local_now_db_expr(), onupdate=local_now_db_func())
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    # Indexes for efficient querying
    __table_args__ = (
        Index('idx_user_metric_date_categorized', 'user_id', 'metric_type', 'start_date'),
        Index('idx_metric_date_range_categorized', 'metric_type', 'start_date', 'end_date'),
        Index('idx_user_source_date_categorized', 'user_id', 'data_source', 'start_date'),
        Index('idx_aggregation_status_categorized', 'aggregation_status', 'user_id', 'start_date'),
        Index('idx_loinc_code_categorized', 'loinc_code'),
        UniqueConstraint('user_id', 'metric_type', 'unit', 'start_date', 'data_source', 'notes', name='uq_vitals_raw_categorized_no_duplicates'),
    )

class VitalsHourlyAggregate(Base):
    """Hourly aggregated vitals data"""
    __tablename__ = "vitals_hourly_aggregates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    metric_type = Column(String, nullable=False)  # Store as string to match enum values
    loinc_code = Column(String(20), nullable=True, index=True)  # LOINC code for standardized vital sign identification
    hour_start = Column(DateTime, nullable=False)  # Start of the hour
    
    # Aggregated values
    total_value = Column(Float)  # Sum (for steps, calories)
    average_value = Column(Float)  # Average (for heart rate, BP)
    min_value = Column(Float)  # Minimum value
    max_value = Column(Float)  # Maximum value
    count = Column(Integer, default=0)  # Number of samples
    
    # Specific metrics
    duration_minutes = Column(Float)  # For workouts, sleep
    unit = Column(String, nullable=False)
    
    # Source tracking
    primary_source = Column(String)  # Most recent/preferred source
    sources_included = Column(String)  # JSON array of sources included
    
    # Metadata
    notes = Column(Text)  # Summary notes
    created_at = Column(DateTime, server_default=local_now_db_expr())
    updated_at = Column(DateTime, server_default=local_now_db_expr(), onupdate=local_now_db_func())
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    # Indexes
    __table_args__ = (
        Index('idx_user_loinc_hourly', 'user_id', 'loinc_code', 'hour_start'),
        Index('idx_hour_loinc', 'hour_start', 'loinc_code'),
    )

class VitalsDailyAggregate(Base):
    """Daily aggregated vitals data"""
    __tablename__ = "vitals_daily_aggregates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    metric_type = Column(String, nullable=False)  # Store as string to match enum values
    loinc_code = Column(String(20), nullable=True, index=True)  # LOINC code for standardized vital sign identification
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
    
    # Source tracking
    primary_source = Column(String)  # Most recent/preferred source
    sources_included = Column(String)  # JSON array of sources included
    
    # Metadata
    notes = Column(Text)  # Summary notes
    created_at = Column(DateTime, server_default=local_now_db_expr())
    updated_at = Column(DateTime, server_default=local_now_db_expr(), onupdate=local_now_db_func())
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    # Indexes
    __table_args__ = (
        Index('idx_user_loinc_daily', 'user_id', 'loinc_code', 'date'),
        Index('idx_date_loinc', 'date', 'loinc_code'),
    )

class VitalsWeeklyAggregate(Base):
    """Weekly aggregated vitals data"""
    __tablename__ = "vitals_weekly_aggregates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    metric_type = Column(String, nullable=False)  # Store as string to match enum values
    loinc_code = Column(String(20), nullable=True, index=True)  # LOINC code for standardized vital sign identification
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
    
    # Source tracking
    primary_source = Column(String)
    sources_included = Column(String)
    
    # Metadata
    notes = Column(Text)
    created_at = Column(DateTime, server_default=local_now_db_expr())
    updated_at = Column(DateTime, server_default=local_now_db_expr(), onupdate=local_now_db_func())
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    # Indexes
    __table_args__ = (
        Index('idx_user_loinc_weekly', 'user_id', 'loinc_code', 'week_start_date'),
    )

class VitalsMonthlyAggregate(Base):
    """Monthly aggregated vitals data"""
    __tablename__ = "vitals_monthly_aggregates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    metric_type = Column(String, nullable=False)  # Store as string to match enum values
    loinc_code = Column(String(20), nullable=True, index=True)  # LOINC code for standardized vital sign identification
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
    
    # Source tracking
    primary_source = Column(String)
    sources_included = Column(String)
    
    # Metadata
    notes = Column(Text)
    created_at = Column(DateTime, server_default=local_now_db_expr())
    updated_at = Column(DateTime, server_default=local_now_db_expr(), onupdate=local_now_db_func())
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    # Indexes
    __table_args__ = (
        Index('idx_user_loinc_monthly', 'user_id', 'loinc_code', 'year', 'month'),
    )

class VitalsSyncStatus(Base):
    """Track vitals sync status for each user and source"""
    __tablename__ = "vitals_sync_status"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    data_source = Column(String, nullable=False)  # Store as string to match enum values
    
    # Sync tracking
    last_sync_date = Column(DateTime)
    last_successful_sync = Column(DateTime)
    sync_enabled = Column(String, default="true")  # "true", "false", "pending"
    
    # Error tracking
    last_error = Column(Text)
    error_count = Column(Integer, default=0)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    # Unique constraint for user + source combination
    __table_args__ = (
        Index('idx_user_source_sync', 'user_id', 'data_source'),
    ) 