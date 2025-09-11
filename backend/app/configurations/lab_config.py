# Lab-related table names configuration
# Based on actual tables found in PostgreSQL database

LAB_TABLES = {
    "lab_reports": "lab_reports",                           # Main lab results table            # Clinical reports table
    "lab_report_categorized": "lab_report_categorized",     # Categorized lab reports
    "lab_reports_daily": "lab_reports_daily",               # Daily aggregated reports
    "lab_reports_monthly": "lab_reports_monthly",           # Monthly aggregated reports
    "lab_reports_quarterly": "lab_reports_quarterly",       # Quarterly aggregated reports
    "lab_reports_yearly": "lab_reports_yearly",             # Yearly aggregated reports
    "lab_test_mappings": "lab_test_mappings"                # Test name mappings
}

# Primary lab table for main operations
PRIMARY_LAB_TABLE = LAB_TABLES["lab_reports"]

# All lab table names as a list
ALL_LAB_TABLES = list(LAB_TABLES.values())

# Aggregation tables for trend analysis
AGGREGATION_TABLES = [
    LAB_TABLES["lab_reports_daily"],
    LAB_TABLES["lab_reports_monthly"], 
    LAB_TABLES["lab_reports_quarterly"],
    LAB_TABLES["lab_reports_yearly"]
] 