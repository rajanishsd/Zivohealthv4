#!/usr/bin/env python3
"""
Vitals Configuration
Defines vitals-related tables, vital sign categories, and measurement mappings for the vitals agent.
"""

# Primary vitals table for storing vital signs records
PRIMARY_VITALS_TABLE = "vitals_raw_data"

# All vitals-related tables
VITALS_TABLES = {
    "vitals_raw_data": "Main table for daily vital signs records",
    "vitals_raw_categorized": "Main table for daily vital signs records",
    "vitals_hourly_aggregates": "hourly vitals aggregates",
    "vitals_daily_aggregates": "daily vitals aggregates",
    "vitals_weekly_aggregates": "weekly vitals aggregates",
    "vitals_monthly_aggregates": "monthly vitals aggregates"
}


# Export all configurations
__all__ = [
    'PRIMARY_VITALS_TABLE',
    'VITALS_TABLES'
] 