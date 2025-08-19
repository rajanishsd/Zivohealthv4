from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from enum import Enum

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

# Request schemas
class VitalDataSubmission(BaseModel):
    """Schema for submitting vital data from any source"""
    metric_type: VitalMetricType
    value: float
    unit: str
    start_date: datetime
    end_date: datetime
    data_source: VitalDataSource
    notes: Optional[str] = None
    source_device: Optional[str] = None
    confidence_score: Optional[float] = None

class VitalBulkSubmission(BaseModel):
    """Schema for bulk submission of vital data"""
    data: List[VitalDataSubmission]
    # Chunk tracking for multi-chunk submissions
    chunk_info: Optional[Dict[str, Any]] = None  # Contains: session_id, chunk_number, total_chunks, is_final_chunk

class VitalDataQuery(BaseModel):
    """Schema for querying vital data"""
    metric_types: Optional[List[VitalMetricType]] = None
    data_sources: Optional[List[VitalDataSource]] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    granularity: TimeGranularity = TimeGranularity.DAILY

# Response schemas
class VitalDataPoint(BaseModel):
    """Single vital data point response"""
    id: int
    metric_type: VitalMetricType
    value: float
    unit: str
    start_date: datetime
    end_date: datetime
    data_source: VitalDataSource
    notes: Optional[str] = None
    source_device: Optional[str] = None
    confidence_score: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True

class VitalAggregateData(BaseModel):
    """Aggregated vital data response"""
    metric_type: VitalMetricType
    date: Optional[str] = None  # For daily - ISO date string
    hour_start: Optional[str] = None  # For hourly - ISO datetime string
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
    
    # Source tracking
    primary_source: Optional[VitalDataSource] = None
    sources_included: Optional[List[str]] = None
    
    # Metadata
    notes: Optional[str] = None
    workout_breakdown: Optional[Dict[str, float]] = None  # For workouts

    class Config:
        from_attributes = True

class VitalMetricSummary(BaseModel):
    """Summary of a specific metric type"""
    metric_type: VitalMetricType
    unit: str
    latest_value: Optional[float] = None
    latest_date: Optional[datetime] = None
    latest_source: Optional[VitalDataSource] = None
    data_points: List[VitalAggregateData]

class VitalsDashboard(BaseModel):
    """Complete vitals dashboard data"""
    user_id: int
    last_sync: Optional[datetime] = None
    metrics: List[VitalMetricSummary]

class VitalsSyncStatusResponse(BaseModel):
    """Sync status response"""
    user_id: int
    data_source: VitalDataSource
    sync_enabled: str
    last_sync_date: Optional[datetime] = None
    last_successful_sync: Optional[datetime] = None
    last_error: Optional[str] = None
    error_count: int = 0

    class Config:
        from_attributes = True

class VitalSubmissionResponse(BaseModel):
    """Response for vital data submission"""
    success: bool
    message: str
    processed_count: int
    aggregation_status: Optional[str] = None  # pending, processing, completed, queued, failed
    errors: Optional[List[str]] = None

class ChartDataPoint(BaseModel):
    """Chart data point for visualization"""
    date: str
    value: float
    min_value: Optional[float] = None  # For heart rate and other range-based metrics
    max_value: Optional[float] = None  # For heart rate and other range-based metrics
    label: Optional[str] = None
    source: Optional[VitalDataSource] = None
    workout_breakdown: Optional[Dict[str, float]] = None

class ChartData(BaseModel):
    """Chart data for visualization"""
    metric_type: VitalMetricType
    unit: str
    granularity: TimeGranularity
    data_points: List[ChartDataPoint]
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    average_value: Optional[float] = None
    total_value: Optional[float] = None

class VitalMetricsChartsResponse(BaseModel):
    """Response containing multiple chart data"""
    user_id: int
    charts: List[ChartData]
    date_range: Dict[str, str]  # start_date, end_date

# Weight-specific schemas for backward compatibility
class WeightUpdateRequest(BaseModel):
    """Schema for updating weight specifically"""
    weight: float
    unit: str = "kg"
    notes: Optional[str] = None
    measurement_date: Optional[datetime] = None

class WeightUpdateResponse(BaseModel):
    """Response for weight update"""
    success: bool
    message: str
    weight_id: int
    weight_value: float
    unit: str
    measurement_date: datetime 