"""Mapping helpers between existing data models and scoring keys.

These functions centralize the mapping so we can evolve anchors/keys without
changing the compute logic.
"""

VITALS_MAP = {
    "Heart Rate": "resting_hr",
    "Blood Pressure Systolic": "bp_systolic",
    "Blood Pressure Diastolic": "bp_diastolic",
    "Oxygen Saturation": "spo2_pct",
    "Temperature": "temperature_c",
}

SLEEP_MAP = {
    "Sleep": "duration_h",
}

ACTIVITY_MAP = {
    "Steps": "steps_per_day",
}

BIOMARKER_LOINC_TO_KEY = {
    # Example entries; full list is maintained in MetricAnchorRegistry table.
    "4548-4": "a1c_pct",  # Hemoglobin A1c/Hemoglobin.total in Blood
    "13457-7": "ldl_mgdl",  # LDL Cholesterol
}


