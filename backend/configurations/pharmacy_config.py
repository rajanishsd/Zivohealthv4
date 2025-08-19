#!/usr/bin/env python3
"""
Pharmacy Configuration
Defines pharmacy-related tables, medication categories, and mappings for the pharmacy agent.
"""

# Primary pharmacy table for storing medication purchase records
PRIMARY_PHARMACY_TABLE = "pharmacy_bills"

# All pharmacy-related tables (using existing tables)
PHARMACY_TABLES = {
    "pharmacy_bills": "Main table for pharmacy bill records",
    "pharmacy_medications": "Detailed medication records from pharmacy bills"
}

# Export all configurations
__all__ = [
    'PRIMARY_PHARMACY_TABLE',
    'PHARMACY_TABLES'
]