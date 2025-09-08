from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date

# Reuse timeframe semantics consistent with nutrition
class GoalTimeframe(str):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class NutritionObjectiveOut(BaseModel):
    code: str
    display_name: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


class NutrientCatalogOut(BaseModel):
    id: int
    key: str
    display_name: str
    category: str
    unit: str
    rda_male: Optional[float] = None
    rda_female: Optional[float] = None
    upper_limit: Optional[float] = None
    is_enabled: bool = True

    class Config:
        from_attributes = True


class NutritionGoalOut(BaseModel):
    id: int
    goal_name: str
    goal_description: Optional[str] = None
    status: str
    effective_at: date
    expires_at: Optional[date] = None
    objective_code: Optional[str] = None  # For backward compatibility with mobile app

    class Config:
        from_attributes = True


class NutritionGoalTargetNutrient(BaseModel):
    id: int
    key: str
    display_name: str


class NutritionGoalTargetOut(BaseModel):
    id: int
    timeframe: str
    target_type: str
    target_min: Optional[float] = None
    target_max: Optional[float] = None
    priority: str
    is_active: bool
    nutrient: NutritionGoalTargetNutrient


class ActiveGoalSummaryOut(BaseModel):
    has_active_goal: bool
    goal: Optional[NutritionGoalOut] = None
    targets_summary: Optional[dict] = None
    focus_nutrients: Optional[List["UserNutrientFocusOut"]] = None


class DefaultTargetOut(BaseModel):
    objective_code: str
    timeframe: str
    target_type: str
    target_min: Optional[float] = None
    target_max: Optional[float] = None
    priority: str
    nutrient: NutritionGoalTargetNutrient


class UserNutrientFocusOut(BaseModel):
    nutrient_id: int
    nutrient_key: str
    priority: str
    is_active: bool


class ProgressItemOut(BaseModel):
    nutrient_key: str
    display_name: str
    unit: str
    priority: str
    target_type: str
    target_min: Optional[float] = None
    target_max: Optional[float] = None
    current_value: Optional[float] = None
    percent_of_target: Optional[float] = None
    status: Optional[str] = None  # below|within|above|no_data


class ProgressResponseOut(BaseModel):
    objective_code: Optional[str] = None
    timeframe: str
    start_date: date
    end_date: date
    items: List[ProgressItemOut]


# Rebuild models to resolve forward references
ActiveGoalSummaryOut.model_rebuild()
