#!/usr/bin/env python3
"""
Add missing metric anchors for health score calculation
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import and_
from app.health_scoring.models import MetricAnchorRegistry
from app.db.session import SessionLocal

def main():
    db = SessionLocal()
    
    print("=" * 80)
    print("ADDING MISSING METRIC ANCHORS FOR HEALTH SCORE")
    print("=" * 80)
    print()
    
    # Define all required metric anchors
    metric_anchors = [
        # Biomarkers
        {
            "domain": "biomarker",
            "key": "a1c_pct",
            "loinc_code": "4548-4",
            "unit": "%",
            "pattern": "lower",
            "anchors": [[5.0, 100], [5.6, 95], [5.7, 90], [6.0, 75], [6.5, 55], [7.0, 45], [8.0, 30], [9.0, 20], [10.0, 10]],
            "half_life_days": 180,
            "group_key": "glycemic",
            "active": True,
            "introduced_in": "v1"
        },
        {
            "domain": "biomarker",
            "key": "ldl_mgdl",
            "loinc_code": "13457-7",
            "unit": "mg/dL",
            "pattern": "lower",
            "anchors": [[70, 100], [100, 90], [130, 70], [160, 45], [190, 25], [220, 10]],
            "half_life_days": 180,
            "group_key": "lipids",
            "active": True,
            "introduced_in": "v1"
        },
        {
            "domain": "biomarker",
            "key": "hdl_mgdl_male",
            "loinc_code": "2085-9",
            "unit": "mg/dL",
            "pattern": "higher",
            "anchors": [[25, 25], [35, 55], [40, 70], [50, 85], [60, 100]],
            "half_life_days": 180,
            "group_key": "lipids",
            "active": True,
            "introduced_in": "v1"
        },
        {
            "domain": "biomarker",
            "key": "triglycerides_mgdl",
            "loinc_code": "2571-8",
            "unit": "mg/dL",
            "pattern": "lower",
            "anchors": [[100, 100], [150, 85], [200, 70], [300, 50], [400, 35], [500, 20], [1000, 5]],
            "half_life_days": 180,
            "group_key": "lipids",
            "active": True,
            "introduced_in": "v1"
        },
        {
            "domain": "biomarker",
            "key": "alt_u_l",
            "loinc_code": "1742-6",
            "unit": "U/L",
            "pattern": "lower",
            "anchors": [[25, 100], [40, 90], [60, 75], [80, 60], [120, 40], [200, 20], [300, 10]],
            "half_life_days": 180,
            "group_key": "hepatic",
            "active": True,
            "introduced_in": "v1"
        },
        {
            "domain": "biomarker",
            "key": "ast_u_l",
            "loinc_code": "1920-8",
            "unit": "U/L",
            "pattern": "lower",
            "anchors": [[25, 100], [40, 90], [60, 75], [80, 60], [120, 40], [200, 20], [300, 10]],
            "half_life_days": 180,
            "group_key": "hepatic",
            "active": True,
            "introduced_in": "v1"
        },
        {
            "domain": "biomarker",
            "key": "hs_crp_mg_l",
            "loinc_code": "30522-7",
            "unit": "mg/L",
            "pattern": "lower",
            "anchors": [[1.0, 100], [3.0, 75], [5.0, 60], [10, 40], [20, 20], [50, 5]],
            "half_life_days": 180,
            "group_key": "inflammation",
            "active": True,
            "introduced_in": "v1"
        },
        {
            "domain": "biomarker",
            "key": "vitd_25oh_ngml",
            "loinc_code": "1989-3",
            "unit": "ng/mL",
            "pattern": "range",
            "anchors": [[10, 10], [15, 30], [20, 50], [25, 65], [30, 100], [50, 100], [60, 90], [80, 70], [100, 50]],
            "half_life_days": 180,
            "group_key": "vitamins",
            "active": True,
            "introduced_in": "v1"
        },
        # Activity
        {
            "domain": "activity",
            "key": "steps_per_day",
            "loinc_code": None,
            "unit": "steps",
            "pattern": "higher",
            "anchors": [[0, 0], [2000, 20], [5000, 50], [7000, 70], [10000, 90], [12000, 95], [15000, 100]],
            "half_life_days": None,
            "group_key": "physical_activity",
            "active": True,
            "introduced_in": "v1"
        },
        # Sleep
        {
            "domain": "sleep",
            "key": "duration_h",
            "loinc_code": None,
            "unit": "hours",
            "pattern": "range",
            "anchors": [[0, 0], [4, 20], [5, 40], [6, 60], [7, 90], [8, 100], [9, 90], [10, 70], [12, 50]],
            "half_life_days": None,
            "group_key": "sleep_quality",
            "active": True,
            "introduced_in": "v1"
        },
        # Vitals
        {
            "domain": "vitals",
            "key": "resting_hr",
            "loinc_code": None,
            "unit": "bpm",
            "pattern": "range",
            "anchors": [[40, 90], [50, 100], [60, 100], [70, 95], [80, 85], [90, 70], [100, 50], [110, 30], [120, 10]],
            "half_life_days": None,
            "group_key": "cardiovascular",
            "active": True,
            "introduced_in": "v1"
        },
        {
            "domain": "vitals",
            "key": "bp_systolic",
            "loinc_code": None,
            "unit": "mmHg",
            "pattern": "range",
            "anchors": [[90, 70], [100, 85], [110, 95], [120, 100], [130, 85], [140, 70], [160, 40], [180, 20], [200, 5]],
            "half_life_days": None,
            "group_key": "cardiovascular",
            "active": True,
            "introduced_in": "v1"
        },
        {
            "domain": "vitals",
            "key": "bp_diastolic",
            "loinc_code": None,
            "unit": "mmHg",
            "pattern": "range",
            "anchors": [[60, 80], [70, 95], [80, 100], [85, 95], [90, 70], [100, 40], [110, 20], [120, 5]],
            "half_life_days": None,
            "group_key": "cardiovascular",
            "active": True,
            "introduced_in": "v1"
        },
        {
            "domain": "vitals",
            "key": "spo2_pct",
            "loinc_code": None,
            "unit": "%",
            "pattern": "higher",
            "anchors": [[85, 0], [90, 30], [92, 50], [95, 80], [97, 95], [98, 100], [100, 100]],
            "half_life_days": None,
            "group_key": "respiratory",
            "active": True,
            "introduced_in": "v1"
        },
        {
            "domain": "vitals",
            "key": "temperature_c",
            "loinc_code": None,
            "unit": "°C",
            "pattern": "range",
            "anchors": [[35.0, 50], [36.0, 80], [36.5, 100], [37.0, 100], [37.5, 90], [38.0, 70], [38.5, 50], [39.0, 30], [40.0, 10]],
            "half_life_days": None,
            "group_key": "general",
            "active": True,
            "introduced_in": "v1"
        },
        # Medication
        {
            "domain": "medication",
            "key": "pdc",
            "loinc_code": None,
            "unit": "ratio",
            "pattern": "higher",
            "anchors": [[0.0, 0], [0.4, 30], [0.6, 60], [0.8, 85], [0.9, 95], [1.0, 100]],
            "half_life_days": None,
            "group_key": "adherence",
            "active": True,
            "introduced_in": "v1"
        },
        # Nutrition
        {
            "domain": "nutrition",
            "key": "energy_balance_pct_abs",
            "loinc_code": None,
            "unit": "%",
            "pattern": "lower",
            "anchors": [[0, 100], [5, 95], [10, 90], [15, 80], [20, 60], [30, 40], [50, 20]],
            "half_life_days": None,
            "group_key": "calorie_balance",
            "active": True,
            "introduced_in": "v1"
        }
    ]
    
    added = 0
    updated = 0
    skipped = 0
    
    for anchor_def in metric_anchors:
        # Check if anchor already exists
        existing = db.query(MetricAnchorRegistry).filter(
            and_(
                MetricAnchorRegistry.domain == anchor_def["domain"],
                MetricAnchorRegistry.key == anchor_def["key"]
            )
        ).first()
        
        if existing:
            # Update if LOINC code is missing
            if anchor_def.get("loinc_code") and not existing.loinc_code:
                existing.loinc_code = anchor_def["loinc_code"]
                existing.group_key = anchor_def["group_key"]
                updated += 1
                print(f"  ✓ Updated: {anchor_def['domain']}.{anchor_def['key']} (added LOINC: {anchor_def['loinc_code']})")
            else:
                skipped += 1
                print(f"  - Skipped: {anchor_def['domain']}.{anchor_def['key']} (already exists)")
        else:
            # Create new anchor
            new_anchor = MetricAnchorRegistry(**anchor_def)
            db.add(new_anchor)
            added += 1
            loinc_info = f" (LOINC: {anchor_def['loinc_code']})" if anchor_def.get('loinc_code') else ""
            print(f"  + Added: {anchor_def['domain']}.{anchor_def['key']}{loinc_info}")
    
    # Commit all changes
    try:
        db.commit()
        print()
        print("=" * 80)
        print(f"✓ SUCCESS: {added} added, {updated} updated, {skipped} skipped")
        print("=" * 80)
    except Exception as e:
        db.rollback()
        print()
        print("=" * 80)
        print(f"✗ ERROR: Failed to commit changes")
        print(f"  {e}")
        print("=" * 80)
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()

