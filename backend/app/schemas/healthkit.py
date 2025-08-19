from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel
from enum import Enum

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
    WORKOUT_DURATION = "Workout Duration"
    WORKOUT_CALORIES = "Workout Calories"
    WORKOUT_DISTANCE = "Workout Distance"
    SLEEP = "Sleep"
    DISTANCE_WALKING = "Distance Walking"

class TimeGranularity(str, Enum):
    """Time granularity for data aggregation"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

# Request schemas
class HealthKitDataSubmission(BaseModel):
    """Schema for submitting HealthKit data from mobile app"""
    metric_type: HealthKitMetricType
    value: float
    unit: str
    start_date: datetime
    end_date: datetime
    notes: Optional[str] = None
    source_device: Optional[str] = None

class HealthKitBulkSubmission(BaseModel):
    """Schema for bulk submission of HealthKit data"""
    data: List[HealthKitDataSubmission]

class HealthKitDataQuery(BaseModel):
    """Schema for querying HealthKit data"""
    metric_types: Optional[List[HealthKitMetricType]] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    granularity: TimeGranularity = TimeGranularity.DAILY

# Response schemas
class HealthKitDataPoint(BaseModel):
    """Single HealthKit data point response"""
    id: int
    metric_type: HealthKitMetricType
    value: float
    unit: str
    start_date: datetime
    end_date: datetime
    notes: Optional[str] = None
    source_device: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class HealthKitAggregateData(BaseModel):
    """Aggregated HealthKit data response"""
    metric_type: HealthKitMetricType
    date: Optional[str] = None  # For daily - ISO date string
    week_start_date: Optional[str] = None  # For weekly - ISO date string
    year: Optional[int] = None  # For monthly
    month: Optional[int] = None  # For monthly
    
    # Aggregated values
    total_value: Optional[float] = None
    average_value: Optional[float] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    count: int = 0
    duration_minutes: Optional[float] = None
    unit: str
    notes: Optional[str] = None
    workout_breakdown: Optional[dict] = None  # For workouts: {"Strength Training": 45.5, "Walking": 30.0}

    class Config:
        from_attributes = True

class HealthKitMetricSummary(BaseModel):
    """Summary of a specific metric type"""
    metric_type: HealthKitMetricType
    unit: str
    latest_value: Optional[float] = None
    latest_date: Optional[datetime] = None
    data_points: List[HealthKitAggregateData]

class HealthKitDashboard(BaseModel):
    """Complete health dashboard data"""
    user_id: int
    last_sync: Optional[datetime] = None
    metrics: List[HealthKitMetricSummary]

class HealthKitSyncStatusResponse(BaseModel):
    """Sync status response"""
    user_id: int
    sync_enabled: str
    last_sync_date: Optional[datetime] = None
    last_successful_sync: Optional[datetime] = None
    last_error: Optional[str] = None
    error_count: int = 0

    class Config:
        from_attributes = True

# Chart data schemas
class ChartDataPoint(BaseModel):
    """Individual data point for charts"""
    date: str  # ISO date string
    value: float
    label: Optional[str] = None  # For categorical data like workout types

class ChartData(BaseModel):
    """Chart data response"""
    metric_type: HealthKitMetricType
    unit: str
    granularity: TimeGranularity
    data_points: List[ChartDataPoint]
    
    # Chart metadata
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    average_value: Optional[float] = None
    total_value: Optional[float] = None

class HealthMetricsChartsResponse(BaseModel):
    """Response containing chart data for multiple metrics"""
    user_id: int
    charts: List[ChartData]
    date_range: dict  # {"start": "2024-01-01", "end": "2024-01-31"}

# Status and error schemas
class HealthKitSubmissionResponse(BaseModel):
    """Response after submitting health data"""
    success: bool
    message: str
    processed_count: int
    errors: Optional[List[str]] = None

class ErrorResponse(BaseModel):
    """Error response schema"""
    error: str
    message: str
    details: Optional[dict] = None 