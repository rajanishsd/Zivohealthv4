from sqlalchemy import Column, Integer, String, Float, DateTime, Date, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from enum import Enum

from app.db.base import Base

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

class DishType(str, Enum):
    """Type of dish for dietary classification"""
    VEGETARIAN = "vegetarian"
    VEGAN = "vegan"
    CHICKEN = "chicken"
    BEEF = "beef"
    FISH = "fish"
    SHELLFISH = "shellfish"
    OTHER = "other"

class TimeGranularity(str, Enum):
    """Time granularity for data aggregation"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

class NutritionRawData(Base):
    """Raw nutrition data from all sources"""
    __tablename__ = "nutrition_raw_data"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Food identification
    food_item_name = Column(String, nullable=False)
    dish_name = Column(String, nullable=True)  # AI-extracted dish name
    dish_type = Column(String, nullable=True)  # vegetarian, vegan, chicken, etc.
    meal_type = Column(String, nullable=False)  # breakfast, lunch, dinner, snack
    portion_size = Column(Float, nullable=False)
    portion_unit = Column(String, nullable=False)  # grams, cups, pieces, etc.
    
    # Nutritional values (per portion)
    calories = Column(Float, nullable=False)
    protein_g = Column(Float, default=0.0)
    fat_g = Column(Float, default=0.0)
    carbs_g = Column(Float, default=0.0)
    fiber_g = Column(Float, default=0.0)
    sugar_g = Column(Float, default=0.0)
    sodium_mg = Column(Float, default=0.0)
    
    # Vitamins (per portion)
    vitamin_a_mcg = Column(Float, default=0.0)
    vitamin_c_mg = Column(Float, default=0.0)
    vitamin_d_mcg = Column(Float, default=0.0)
    vitamin_e_mg = Column(Float, default=0.0)
    vitamin_k_mcg = Column(Float, default=0.0)
    vitamin_b1_mg = Column(Float, default=0.0)  # Thiamine
    vitamin_b2_mg = Column(Float, default=0.0)  # Riboflavin
    vitamin_b3_mg = Column(Float, default=0.0)  # Niacin
    vitamin_b6_mg = Column(Float, default=0.0)
    vitamin_b12_mcg = Column(Float, default=0.0)
    folate_mcg = Column(Float, default=0.0)
    
    # Minerals (per portion)
    calcium_mg = Column(Float, default=0.0)
    iron_mg = Column(Float, default=0.0)
    magnesium_mg = Column(Float, default=0.0)
    phosphorus_mg = Column(Float, default=0.0)
    potassium_mg = Column(Float, default=0.0)
    zinc_mg = Column(Float, default=0.0)
    copper_mg = Column(Float, default=0.0)
    manganese_mg = Column(Float, default=0.0)
    selenium_mcg = Column(Float, default=0.0)
    
    # Timing
    meal_date = Column(Date, nullable=False)
    meal_time = Column(DateTime, nullable=False)
    
    # Source tracking
    data_source = Column(String, nullable=False)  # Store as string to match enum values
    confidence_score = Column(Float)  # AI analysis confidence (0.0-1.0)
    image_url = Column(String)  # Reference to uploaded photo
    
    # Metadata
    notes = Column(Text)  # Additional notes, cooking method, etc.
    
    # Aggregation tracking
    aggregation_status = Column(String(20), nullable=False, default='pending')  # pending, processing, completed, failed
    aggregated_at = Column(DateTime, nullable=True)
    
    # Tracking
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    # Indexes for efficient querying
    __table_args__ = (
        Index('idx_nutrition_user_meal_date', 'user_id', 'meal_date'),
        Index('idx_nutrition_meal_date_range', 'meal_date', 'meal_time'),
        Index('idx_nutrition_user_source_date', 'user_id', 'data_source', 'meal_date'),
        Index('idx_nutrition_aggregation_status', 'aggregation_status', 'user_id', 'meal_date'),
        Index('idx_nutrition_meal_type_date', 'meal_type', 'meal_date'),
    )


class NutritionDailyAggregate(Base):
    """Daily aggregated nutrition data"""
    __tablename__ = "nutrition_daily_aggregates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(Date, nullable=False)
    
    # Aggregated nutritional values
    total_calories = Column(Float, default=0.0)
    total_protein_g = Column(Float, default=0.0)
    total_fat_g = Column(Float, default=0.0)
    total_carbs_g = Column(Float, default=0.0)
    total_fiber_g = Column(Float, default=0.0)
    total_sugar_g = Column(Float, default=0.0)
    total_sodium_mg = Column(Float, default=0.0)
    
    # Vitamins totals
    total_vitamin_a_mcg = Column(Float, default=0.0)
    total_vitamin_c_mg = Column(Float, default=0.0)
    total_vitamin_d_mcg = Column(Float, default=0.0)
    total_vitamin_e_mg = Column(Float, default=0.0)
    total_vitamin_k_mcg = Column(Float, default=0.0)
    total_vitamin_b1_mg = Column(Float, default=0.0)  # Thiamine
    total_vitamin_b2_mg = Column(Float, default=0.0)  # Riboflavin
    total_vitamin_b3_mg = Column(Float, default=0.0)  # Niacin
    total_vitamin_b6_mg = Column(Float, default=0.0)
    total_vitamin_b12_mcg = Column(Float, default=0.0)
    total_folate_mcg = Column(Float, default=0.0)
    
    # Minerals totals
    total_calcium_mg = Column(Float, default=0.0)
    total_iron_mg = Column(Float, default=0.0)
    total_magnesium_mg = Column(Float, default=0.0)
    total_phosphorus_mg = Column(Float, default=0.0)
    total_potassium_mg = Column(Float, default=0.0)
    total_zinc_mg = Column(Float, default=0.0)
    total_copper_mg = Column(Float, default=0.0)
    total_manganese_mg = Column(Float, default=0.0)
    total_selenium_mcg = Column(Float, default=0.0)
    
    # Meal breakdown
    meal_count = Column(Integer, default=0)
    breakfast_count = Column(Integer, default=0)
    lunch_count = Column(Integer, default=0)
    dinner_count = Column(Integer, default=0)
    snack_count = Column(Integer, default=0)
    
    # Meal-specific calories
    breakfast_calories = Column(Float, default=0.0)
    lunch_calories = Column(Float, default=0.0)
    dinner_calories = Column(Float, default=0.0)
    snack_calories = Column(Float, default=0.0)
    
    # Source tracking
    primary_source = Column(String)  # Most recent/preferred source
    sources_included = Column(String)  # JSON array of sources included
    
    # Metadata
    notes = Column(Text)  # Summary notes
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    # Indexes
    __table_args__ = (
        Index('idx_nutrition_user_daily', 'user_id', 'date'),
        Index('idx_nutrition_date_daily', 'date'),
    )

class NutritionWeeklyAggregate(Base):
    """Weekly aggregated nutrition data"""
    __tablename__ = "nutrition_weekly_aggregates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    week_start_date = Column(Date, nullable=False)  # Monday of the week
    week_end_date = Column(Date, nullable=False)    # Sunday of the week
    
    # Average daily nutritional values
    avg_daily_calories = Column(Float, default=0.0)
    avg_daily_protein_g = Column(Float, default=0.0)
    avg_daily_fat_g = Column(Float, default=0.0)
    avg_daily_carbs_g = Column(Float, default=0.0)
    avg_daily_fiber_g = Column(Float, default=0.0)
    avg_daily_sugar_g = Column(Float, default=0.0)
    avg_daily_sodium_mg = Column(Float, default=0.0)
    
    # Average daily vitamins
    avg_daily_vitamin_a_mcg = Column(Float, default=0.0)
    avg_daily_vitamin_c_mg = Column(Float, default=0.0)
    avg_daily_vitamin_d_mcg = Column(Float, default=0.0)
    avg_daily_vitamin_e_mg = Column(Float, default=0.0)
    avg_daily_vitamin_k_mcg = Column(Float, default=0.0)
    avg_daily_vitamin_b1_mg = Column(Float, default=0.0)
    avg_daily_vitamin_b2_mg = Column(Float, default=0.0)
    avg_daily_vitamin_b3_mg = Column(Float, default=0.0)
    avg_daily_vitamin_b6_mg = Column(Float, default=0.0)
    avg_daily_vitamin_b12_mcg = Column(Float, default=0.0)
    avg_daily_folate_mcg = Column(Float, default=0.0)
    
    # Average daily minerals
    avg_daily_calcium_mg = Column(Float, default=0.0)
    avg_daily_iron_mg = Column(Float, default=0.0)
    avg_daily_magnesium_mg = Column(Float, default=0.0)
    avg_daily_phosphorus_mg = Column(Float, default=0.0)
    avg_daily_potassium_mg = Column(Float, default=0.0)
    avg_daily_zinc_mg = Column(Float, default=0.0)
    avg_daily_copper_mg = Column(Float, default=0.0)
    avg_daily_manganese_mg = Column(Float, default=0.0)
    avg_daily_selenium_mcg = Column(Float, default=0.0)
    
    # Weekly totals
    total_weekly_calories = Column(Float, default=0.0)
    total_weekly_meals = Column(Integer, default=0)
    days_with_data = Column(Integer, default=0)
    
    # Source tracking
    primary_source = Column(String)
    sources_included = Column(String)
    
    # Metadata
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    # Indexes
    __table_args__ = (
        Index('idx_user_nutrition_weekly', 'user_id', 'week_start_date'),
    )

class NutritionMonthlyAggregate(Base):
    """Monthly aggregated nutrition data"""
    __tablename__ = "nutrition_monthly_aggregates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)  # 1-12
    
    # Average daily nutritional values
    avg_daily_calories = Column(Float, default=0.0)
    avg_daily_protein_g = Column(Float, default=0.0)
    avg_daily_fat_g = Column(Float, default=0.0)
    avg_daily_carbs_g = Column(Float, default=0.0)
    avg_daily_fiber_g = Column(Float, default=0.0)
    avg_daily_sugar_g = Column(Float, default=0.0)
    avg_daily_sodium_mg = Column(Float, default=0.0)
    
    # Average daily vitamins
    avg_daily_vitamin_a_mcg = Column(Float, default=0.0)
    avg_daily_vitamin_c_mg = Column(Float, default=0.0)
    avg_daily_vitamin_d_mcg = Column(Float, default=0.0)
    avg_daily_vitamin_e_mg = Column(Float, default=0.0)
    avg_daily_vitamin_k_mcg = Column(Float, default=0.0)
    avg_daily_vitamin_b1_mg = Column(Float, default=0.0)
    avg_daily_vitamin_b2_mg = Column(Float, default=0.0)
    avg_daily_vitamin_b3_mg = Column(Float, default=0.0)
    avg_daily_vitamin_b6_mg = Column(Float, default=0.0)
    avg_daily_vitamin_b12_mcg = Column(Float, default=0.0)
    avg_daily_folate_mcg = Column(Float, default=0.0)
    
    # Average daily minerals
    avg_daily_calcium_mg = Column(Float, default=0.0)
    avg_daily_iron_mg = Column(Float, default=0.0)
    avg_daily_magnesium_mg = Column(Float, default=0.0)
    avg_daily_phosphorus_mg = Column(Float, default=0.0)
    avg_daily_potassium_mg = Column(Float, default=0.0)
    avg_daily_zinc_mg = Column(Float, default=0.0)
    avg_daily_copper_mg = Column(Float, default=0.0)
    avg_daily_manganese_mg = Column(Float, default=0.0)
    avg_daily_selenium_mcg = Column(Float, default=0.0)
    
    # Monthly totals
    total_monthly_calories = Column(Float, default=0.0)
    total_monthly_meals = Column(Integer, default=0)
    days_with_data = Column(Integer, default=0)
    
    # Source tracking
    primary_source = Column(String)
    sources_included = Column(String)
    
    # Metadata
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    # Indexes
    __table_args__ = (
        Index('idx_user_nutrition_monthly', 'user_id', 'year', 'month'),
    )

class NutritionSyncStatus(Base):
    """Track nutrition sync status for each user and source"""
    __tablename__ = "nutrition_sync_status"

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
        Index('idx_user_source_nutrition', 'user_id', 'data_source'),
    ) 