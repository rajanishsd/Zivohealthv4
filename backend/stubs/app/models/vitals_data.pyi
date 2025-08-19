# Type stub for vitals data models
from typing import Any, Optional, List
from datetime import datetime, date

class VitalsRawData:
    def __init__(self, **kwargs: Any) -> None: ...
    id: int
    user_id: int
    metric_type: str
    value: float
    unit: str
    start_date: datetime
    end_date: datetime
    data_source: str
    source_device: Optional[str]
    notes: Optional[str]
    confidence_score: Optional[float]
    aggregation_status: str
    aggregated_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

class VitalsRawCategorized:
    def __init__(self, **kwargs: Any) -> None: ...
    id: int
    user_id: int
    metric_type: str
    value: float
    unit: str
    start_date: datetime
    end_date: datetime
    data_source: str
    source_device: Optional[str]
    loinc_code: Optional[str]
    notes: Optional[str]
    confidence_score: Optional[float]
    aggregation_status: str
    aggregated_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

class VitalsHourlyAggregate:
    def __init__(self, **kwargs: Any) -> None: ...
    id: int
    user_id: int
    metric_type: str
    loinc_code: Optional[str]
    hour_start: datetime
    total_value: Optional[float]
    average_value: Optional[float]
    min_value: Optional[float]
    max_value: Optional[float]
    count: int
    duration_minutes: Optional[float]
    unit: str
    primary_source: Optional[str]
    sources_included: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

class VitalsDailyAggregate:
    def __init__(self, **kwargs: Any) -> None: ...
    id: int
    user_id: int
    metric_type: str
    loinc_code: Optional[str]
    date: date
    total_value: Optional[float]
    average_value: Optional[float]
    min_value: Optional[float]
    max_value: Optional[float]
    count: int
    duration_minutes: Optional[float]
    unit: str
    primary_source: Optional[str]
    sources_included: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

class VitalsWeeklyAggregate:
    def __init__(self, **kwargs: Any) -> None: ...
    id: int
    user_id: int
    metric_type: str
    loinc_code: Optional[str]
    week_start_date: date
    week_end_date: date
    total_value: Optional[float]
    average_value: Optional[float]
    min_value: Optional[float]
    max_value: Optional[float]
    days_with_data: int
    total_duration_minutes: Optional[float]
    unit: str
    primary_source: Optional[str]
    sources_included: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

class VitalsMonthlyAggregate:
    def __init__(self, **kwargs: Any) -> None: ...
    id: int
    user_id: int
    metric_type: str
    loinc_code: Optional[str]
    year: int
    month: int
    total_value: Optional[float]
    average_value: Optional[float]
    min_value: Optional[float]
    max_value: Optional[float]
    days_with_data: int
    total_duration_minutes: Optional[float]
    unit: str
    primary_source: Optional[str]
    sources_included: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

class VitalsSyncStatus:
    def __init__(self, **kwargs: Any) -> None: ...
    id: int
    user_id: int
    data_source: str
    last_sync_date: Optional[datetime]
    success: bool
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime 