from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from enum import Enum

# Enums
class NutritionDataSource(str, Enum):
    """Source of nutrition data"""
    PHOTO_ANALYSIS = "photo_analysis"
    MANUAL_ENTRY = "manual_entry"
    BARCODE_SCAN = "barcode_scan"
    RECIPE_IMPORT = "recipe_import"
    API_IMPORT = "api_import"

class MealType(str, Enum):
    """Type of meal"""
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"
    OTHER = "other"

class TimeGranularity(str, Enum):
    """Time granularity for data aggregation"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

# Base schemas
class NutritionDataBase(BaseModel):
    """Base schema for nutrition data"""
    food_item_name: str = Field(..., description="Name of the food item")
    meal_type: MealType = Field(..., description="Type of meal")
    portion_size: float = Field(..., gt=0, description="Portion size")
    portion_unit: str = Field(..., description="Unit of portion (grams, cups, pieces, etc.)")
    
    # Nutritional values
    calories: float = Field(..., ge=0, description="Calories per portion")
    protein_g: Optional[float] = Field(0.0, ge=0, description="Protein in grams")
    fat_g: Optional[float] = Field(0.0, ge=0, description="Fat in grams")
    carbs_g: Optional[float] = Field(0.0, ge=0, description="Carbohydrates in grams")
    fiber_g: Optional[float] = Field(0.0, ge=0, description="Fiber in grams")
    sugar_g: Optional[float] = Field(0.0, ge=0, description="Sugar in grams")
    sodium_mg: Optional[float] = Field(0.0, ge=0, description="Sodium in milligrams")
    
    # Vitamins (per portion)
    vitamin_a_mcg: Optional[float] = Field(0.0, ge=0, description="Vitamin A in micrograms")
    vitamin_c_mg: Optional[float] = Field(0.0, ge=0, description="Vitamin C in milligrams")
    vitamin_d_mcg: Optional[float] = Field(0.0, ge=0, description="Vitamin D in micrograms")
    vitamin_e_mg: Optional[float] = Field(0.0, ge=0, description="Vitamin E in milligrams")
    vitamin_k_mcg: Optional[float] = Field(0.0, ge=0, description="Vitamin K in micrograms")
    vitamin_b1_mg: Optional[float] = Field(0.0, ge=0, description="Thiamine (B1) in milligrams")
    vitamin_b2_mg: Optional[float] = Field(0.0, ge=0, description="Riboflavin (B2) in milligrams")
    vitamin_b3_mg: Optional[float] = Field(0.0, ge=0, description="Niacin (B3) in milligrams")
    vitamin_b6_mg: Optional[float] = Field(0.0, ge=0, description="Vitamin B6 in milligrams")
    vitamin_b12_mcg: Optional[float] = Field(0.0, ge=0, description="Vitamin B12 in micrograms")
    folate_mcg: Optional[float] = Field(0.0, ge=0, description="Folate in micrograms")
    
    # Minerals (per portion)
    calcium_mg: Optional[float] = Field(0.0, ge=0, description="Calcium in milligrams")
    iron_mg: Optional[float] = Field(0.0, ge=0, description="Iron in milligrams")
    magnesium_mg: Optional[float] = Field(0.0, ge=0, description="Magnesium in milligrams")
    phosphorus_mg: Optional[float] = Field(0.0, ge=0, description="Phosphorus in milligrams")
    potassium_mg: Optional[float] = Field(0.0, ge=0, description="Potassium in milligrams")
    zinc_mg: Optional[float] = Field(0.0, ge=0, description="Zinc in milligrams")
    copper_mg: Optional[float] = Field(0.0, ge=0, description="Copper in milligrams")
    manganese_mg: Optional[float] = Field(0.0, ge=0, description="Manganese in milligrams")
    selenium_mcg: Optional[float] = Field(0.0, ge=0, description="Selenium in micrograms")
    
    # Timing
    meal_date: date = Field(..., description="Date of the meal")
    meal_time: datetime = Field(..., description="Time of the meal")
    
    # Source tracking
    data_source: NutritionDataSource = Field(..., description="Source of the data")
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="AI confidence score")
    image_url: Optional[str] = Field(None, description="URL to uploaded photo")
    
    # Metadata
    notes: Optional[str] = Field(None, description="Additional notes")

class NutritionDataCreate(NutritionDataBase):
    """Schema for creating nutrition data"""
    pass

class NutritionDataUpdate(BaseModel):
    """Schema for updating nutrition data"""
    food_item_name: Optional[str] = None
    meal_type: Optional[MealType] = None
    portion_size: Optional[float] = Field(None, gt=0)
    portion_unit: Optional[str] = None
    
    # Nutritional values
    calories: Optional[float] = Field(None, ge=0)
    protein_g: Optional[float] = Field(None, ge=0)
    fat_g: Optional[float] = Field(None, ge=0)
    carbs_g: Optional[float] = Field(None, ge=0)
    fiber_g: Optional[float] = Field(None, ge=0)
    sugar_g: Optional[float] = Field(None, ge=0)
    sodium_mg: Optional[float] = Field(None, ge=0)
    
    # Vitamins (per portion)
    vitamin_a_mcg: Optional[float] = Field(None, ge=0)
    vitamin_c_mg: Optional[float] = Field(None, ge=0)
    vitamin_d_mcg: Optional[float] = Field(None, ge=0)
    vitamin_e_mg: Optional[float] = Field(None, ge=0)
    vitamin_k_mcg: Optional[float] = Field(None, ge=0)
    vitamin_b1_mg: Optional[float] = Field(None, ge=0)
    vitamin_b2_mg: Optional[float] = Field(None, ge=0)
    vitamin_b3_mg: Optional[float] = Field(None, ge=0)
    vitamin_b6_mg: Optional[float] = Field(None, ge=0)
    vitamin_b12_mcg: Optional[float] = Field(None, ge=0)
    folate_mcg: Optional[float] = Field(None, ge=0)
    
    # Minerals (per portion)
    calcium_mg: Optional[float] = Field(None, ge=0)
    iron_mg: Optional[float] = Field(None, ge=0)
    magnesium_mg: Optional[float] = Field(None, ge=0)
    phosphorus_mg: Optional[float] = Field(None, ge=0)
    potassium_mg: Optional[float] = Field(None, ge=0)
    zinc_mg: Optional[float] = Field(None, ge=0)
    copper_mg: Optional[float] = Field(None, ge=0)
    manganese_mg: Optional[float] = Field(None, ge=0)
    selenium_mcg: Optional[float] = Field(None, ge=0)
    
    # Timing
    meal_date: Optional[date] = None
    meal_time: Optional[datetime] = None
    
    # Source tracking
    data_source: Optional[NutritionDataSource] = None
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    image_url: Optional[str] = None
    
    # Metadata
    notes: Optional[str] = None

class NutritionDataResponse(NutritionDataBase):
    """Schema for nutrition data response"""
    id: int
    user_id: int
    aggregation_status: str
    aggregated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Chart data schemas
class NutritionChartDataPoint(BaseModel):
    """Schema for nutrition chart data points"""
    date: date
    calories: float
    protein_g: float
    fat_g: float
    carbs_g: float
    fiber_g: float
    sugar_g: float
    sodium_mg: float
    meal_count: int

    # Vitamins
    vitamin_a_mcg: float = 0.0
    vitamin_c_mg: float = 0.0
    vitamin_d_mcg: float = 0.0
    vitamin_e_mg: float = 0.0
    vitamin_k_mcg: float = 0.0
    vitamin_b1_mg: float = 0.0
    vitamin_b2_mg: float = 0.0
    vitamin_b3_mg: float = 0.0
    vitamin_b6_mg: float = 0.0
    vitamin_b12_mcg: float = 0.0
    folate_mcg: float = 0.0
    
    # Minerals
    calcium_mg: float = 0.0
    iron_mg: float = 0.0
    magnesium_mg: float = 0.0
    phosphorus_mg: float = 0.0
    potassium_mg: float = 0.0
    zinc_mg: float = 0.0
    copper_mg: float = 0.0
    manganese_mg: float = 0.0
    selenium_mcg: float = 0.0

class NutritionChartData(BaseModel):
    """Schema for nutrition chart data"""
    data_points: List[NutritionChartDataPoint]
    granularity: TimeGranularity
    start_date: date
    end_date: date
    total_days: int
    
    # Summary statistics - Macronutrients
    avg_daily_calories: float
    avg_daily_protein_g: float
    avg_daily_fat_g: float
    avg_daily_carbs_g: float
    avg_daily_fiber_g: float
    avg_daily_sugar_g: float
    avg_daily_sodium_mg: float
    
    # Summary statistics - Vitamins
    avg_daily_vitamin_a_mcg: float = 0.0
    avg_daily_vitamin_c_mg: float = 0.0
    avg_daily_vitamin_d_mcg: float = 0.0
    avg_daily_vitamin_e_mg: float = 0.0
    avg_daily_vitamin_k_mcg: float = 0.0
    avg_daily_vitamin_b1_mg: float = 0.0
    avg_daily_vitamin_b2_mg: float = 0.0
    avg_daily_vitamin_b3_mg: float = 0.0
    avg_daily_vitamin_b6_mg: float = 0.0
    avg_daily_vitamin_b12_mcg: float = 0.0
    avg_daily_folate_mcg: float = 0.0
    
    # Summary statistics - Minerals
    avg_daily_calcium_mg: float = 0.0
    avg_daily_iron_mg: float = 0.0
    avg_daily_magnesium_mg: float = 0.0
    avg_daily_phosphorus_mg: float = 0.0
    avg_daily_potassium_mg: float = 0.0
    avg_daily_zinc_mg: float = 0.0
    avg_daily_copper_mg: float = 0.0
    avg_daily_manganese_mg: float = 0.0
    avg_daily_selenium_mcg: float = 0.0
    
    total_meals: int

# Query parameters
class NutritionQueryParams(BaseModel):
    """Schema for nutrition data query parameters"""
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    meal_type: Optional[MealType] = None
    data_source: Optional[NutritionDataSource] = None
    granularity: TimeGranularity = TimeGranularity.DAILY
    limit: Optional[int] = Field(100, ge=1, le=1000)
    offset: Optional[int] = Field(0, ge=0)
