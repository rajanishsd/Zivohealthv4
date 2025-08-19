from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import date, datetime

# Base schemas
class HealthIndicatorCategoryBase(BaseModel):
    name: str = Field(..., description="Category name")
    description: Optional[str] = Field(None, description="Category description")

class HealthIndicatorCategoryCreate(HealthIndicatorCategoryBase):
    pass

class HealthIndicatorCategory(HealthIndicatorCategoryBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class HealthIndicatorBase(BaseModel):
    name: str = Field(..., description="Indicator name")
    unit: Optional[str] = Field(None, description="Unit of measurement")
    normal_range_min: Optional[float] = Field(None, description="Normal range minimum")
    normal_range_max: Optional[float] = Field(None, description="Normal range maximum")
    data_type: str = Field(default="numeric", description="Data type: numeric, text, boolean, file")

class HealthIndicatorCreate(HealthIndicatorBase):
    category_id: int

class HealthIndicator(HealthIndicatorBase):
    id: int
    category_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    category: Optional[HealthIndicatorCategory] = None

    class Config:
        from_attributes = True

class HealthIndicatorWithCategory(HealthIndicator):
    category: HealthIndicatorCategory

# Patient Health Record schemas
class PatientHealthRecordBase(BaseModel):
    numeric_value: Optional[float] = Field(None, description="Numeric value")
    text_value: Optional[str] = Field(None, description="Text value")
    boolean_value: Optional[bool] = Field(None, description="Boolean value")
    file_path: Optional[str] = Field(None, description="File path for images/reports")
    recorded_date: date = Field(..., description="Date when the value was recorded")
    notes: Optional[str] = Field(None, description="Additional notes")

class PatientHealthRecordCreate(PatientHealthRecordBase):
    indicator_id: int = Field(..., description="Health indicator ID")

class PatientHealthRecordUpdate(BaseModel):
    numeric_value: Optional[float] = None
    text_value: Optional[str] = None
    boolean_value: Optional[bool] = None
    file_path: Optional[str] = None
    recorded_date: Optional[date] = None
    notes: Optional[str] = None

class PatientHealthRecord(PatientHealthRecordBase):
    id: int
    patient_id: int
    indicator_id: int
    recorded_by: Optional[int]
    is_abnormal: bool
    created_at: datetime
    updated_at: datetime
    indicator: Optional[HealthIndicator] = None

    class Config:
        from_attributes = True

class PatientHealthRecordWithIndicator(PatientHealthRecord):
    indicator: HealthIndicatorWithCategory

# Health Data History schemas
class HealthDataHistory(BaseModel):
    id: int
    patient_id: int
    indicator_id: int
    current_record_id: int
    numeric_value: Optional[float]
    text_value: Optional[str]
    boolean_value: Optional[bool]
    file_path: Optional[str]
    recorded_date: date
    recorded_by: Optional[int]
    notes: Optional[str]
    is_abnormal: bool
    change_type: str
    previous_value: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

# Dashboard schemas
class IndicatorSummary(BaseModel):
    indicator_id: int
    indicator_name: str
    unit: Optional[str]
    normal_range_min: Optional[float]
    normal_range_max: Optional[float]
    current_value: Dict[str, Any]
    recorded_date: str
    is_abnormal: bool
    notes: Optional[str]

class CategorySummary(BaseModel):
    category_id: int
    indicators: List[IndicatorSummary]

class PatientDashboard(BaseModel):
    patient_id: int
    total_indicators: int
    abnormal_indicators: int
    health_score: float
    categories: Dict[str, CategorySummary]
    last_updated: str

# Patient Health Summary schemas
class PatientHealthSummary(BaseModel):
    id: int
    patient_id: int
    total_indicators_tracked: int
    abnormal_indicators_count: int
    last_updated: Optional[datetime]
    health_score: Optional[float]
    high_risk_indicators: Optional[str]
    medium_risk_indicators: Optional[str]
    improving_trends: Optional[str]
    declining_trends: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Bulk data input schemas
class BulkHealthDataCreate(BaseModel):
    patient_id: int
    recorded_date: date
    recorded_by: Optional[int] = None
    data: List[Dict[str, Any]] = Field(
        ..., 
        description="List of health data entries with indicator_id and value fields"
    )

class BulkHealthDataResponse(BaseModel):
    created_count: int
    updated_count: int
    errors: List[str]
    records: List[PatientHealthRecord]

# Search and filter schemas
class HealthRecordFilters(BaseModel):
    patient_id: Optional[int] = None
    category_id: Optional[int] = None
    indicator_id: Optional[int] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    is_abnormal: Optional[bool] = None
    skip: int = 0
    limit: int = 100

class HealthDataTrend(BaseModel):
    indicator_id: int
    indicator_name: str
    unit: Optional[str]
    data_points: List[Dict[str, Any]]
    trend_direction: str  # "improving", "declining", "stable"
    average_change: Optional[float]

class PatientHealthTrends(BaseModel):
    patient_id: int
    period_days: int
    trends: List[HealthDataTrend]
    overall_trend: str 