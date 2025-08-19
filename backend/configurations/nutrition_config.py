#!/usr/bin/env python3
"""
Nutrition Configuration
Defines nutrition-related tables, food categories, and nutrient mappings for the nutrition agent.
"""

# Primary nutrition table for storing food intake records
PRIMARY_NUTRITION_TABLE = "nutrition_raw_data"

# All nutrition-related tables
NUTRITION_TABLES = {
    "nutrition_raw_data": "Main table for daily food intake records",
    "nutrition_weekly_aggregates": "weekly nutrition aggregates",
    "nutrition_monthly_aggregates": "monthly nutrition aggregates",
    "nutrition_daily_aggregates": "daily nutrition aggregates"
   
}


# Export all configurations
__all__ = [
    'PRIMARY_NUTRITION_TABLE'
] 