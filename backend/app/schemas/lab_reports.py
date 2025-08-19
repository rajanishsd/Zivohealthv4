from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import date, datetime
from enum import Enum

class LabTestStatus(str, Enum):
    GREEN = "green"
    AMBER = "amber" 
    RED = "red"

class LabTestCategoryResponse(BaseModel):
    category: str
    total_tests: int
    green_count: int
    amber_count: int
    red_count: int

class LabTestResultResponse(BaseModel):
    id: int
    test_name: str
    test_category: str
    value: Optional[float]
    unit: Optional[str]
    normal_range_min: Optional[float]
    normal_range_max: Optional[float]
    status: LabTestStatus
    date: date
    created_at: datetime

class LabCategoryDetailResponse(BaseModel):
    category: str
    tests: List[LabTestResultResponse]
    summary: Dict[str, Any]

class LabReportCategoriesResponse(BaseModel):
    categories: List[LabTestCategoryResponse]
    
    class Config:
        from_attributes = True
