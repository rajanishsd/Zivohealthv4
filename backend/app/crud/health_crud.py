from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func
from datetime import date, datetime, timedelta
from app.models.health_indicator import (
    HealthIndicatorCategory,
    HealthIndicator,
    PatientHealthRecord,
    HealthDataHistory,
    PatientHealthSummary
)
import json

# Health Indicator Category CRUD
def get_health_categories(db: Session, skip: int = 0, limit: int = 100) -> List[HealthIndicatorCategory]:
    """Get all health indicator categories"""
    return db.query(HealthIndicatorCategory).filter(
        HealthIndicatorCategory.is_active == True
    ).offset(skip).limit(limit).all()

def get_health_category(db: Session, category_id: int) -> Optional[HealthIndicatorCategory]:
    """Get a specific health indicator category"""
    return db.query(HealthIndicatorCategory).filter(
        HealthIndicatorCategory.id == category_id
    ).first()

# Health Indicator CRUD
def get_health_indicators(
    db: Session, 
    category_id: Optional[int] = None, 
    skip: int = 0, 
    limit: int = 100
) -> List[HealthIndicator]:
    """Get health indicators with optional category filter"""
    query = db.query(HealthIndicator).filter(HealthIndicator.is_active == True)
    
    if category_id:
        query = query.filter(HealthIndicator.category_id == category_id)
    
    return query.offset(skip).limit(limit).all()

def get_health_indicator(db: Session, indicator_id: int) -> Optional[HealthIndicator]:
    """Get a specific health indicator"""
    return db.query(HealthIndicator).filter(
        HealthIndicator.id == indicator_id
    ).first()

# Patient Health Record CRUD
def create_patient_health_record(
    db: Session,
    patient_id: int,
    indicator_id: int,
    value_data: Dict[str, Any],
    recorded_date: date,
    recorded_by: int,
    notes: Optional[str] = None
) -> PatientHealthRecord:
    """Create a new patient health record"""
    
    # Check if record already exists for this patient-indicator combination
    existing_record = db.query(PatientHealthRecord).filter(
        and_(
            PatientHealthRecord.patient_id == patient_id,
            PatientHealthRecord.indicator_id == indicator_id
        )
    ).first()
    
    if existing_record:
        # Create history record before updating
        history_record = HealthDataHistory(
            patient_id=patient_id,
            indicator_id=indicator_id,
            current_record_id=existing_record.id,
            numeric_value=existing_record.numeric_value,
            text_value=existing_record.text_value,
            boolean_value=existing_record.boolean_value,
            file_path=existing_record.file_path,
            recorded_date=existing_record.recorded_date,
            recorded_by=existing_record.recorded_by,
            notes=existing_record.notes,
            is_abnormal=existing_record.is_abnormal,
            change_type="update",
            previous_value=json.dumps({
                "numeric_value": existing_record.numeric_value,
                "text_value": existing_record.text_value,
                "boolean_value": existing_record.boolean_value,
                "file_path": existing_record.file_path
            })
        )
        db.add(history_record)
        
        # Update existing record
        existing_record.numeric_value = value_data.get("numeric_value")
        existing_record.text_value = value_data.get("text_value")
        existing_record.boolean_value = value_data.get("boolean_value")
        existing_record.file_path = value_data.get("file_path")
        existing_record.recorded_date = recorded_date
        existing_record.recorded_by = recorded_by
        existing_record.notes = notes
        existing_record.updated_at = datetime.utcnow()
        
        # Check if value is abnormal
        indicator = get_health_indicator(db, indicator_id)
        if indicator and value_data.get("numeric_value"):
            numeric_val = value_data["numeric_value"]
            is_abnormal = False
            if indicator.normal_range_min and numeric_val < indicator.normal_range_min:
                is_abnormal = True
            if indicator.normal_range_max and numeric_val > indicator.normal_range_max:
                is_abnormal = True
            existing_record.is_abnormal = is_abnormal
        
        db.commit()
        db.refresh(existing_record)
        return existing_record
    else:
        # Create new record
        db_record = PatientHealthRecord(
            patient_id=patient_id,
            indicator_id=indicator_id,
            numeric_value=value_data.get("numeric_value"),
            text_value=value_data.get("text_value"),
            boolean_value=value_data.get("boolean_value"),
            file_path=value_data.get("file_path"),
            recorded_date=recorded_date,
            recorded_by=recorded_by,
            notes=notes
        )
        
        # Check if value is abnormal
        indicator = get_health_indicator(db, indicator_id)
        if indicator and value_data.get("numeric_value"):
            numeric_val = value_data["numeric_value"]
            is_abnormal = False
            if indicator.normal_range_min and numeric_val < indicator.normal_range_min:
                is_abnormal = True
            if indicator.normal_range_max and numeric_val > indicator.normal_range_max:
                is_abnormal = True
            db_record.is_abnormal = is_abnormal
        
        db.add(db_record)
        db.commit()
        db.refresh(db_record)
        
        # Create initial history record
        history_record = HealthDataHistory(
            patient_id=patient_id,
            indicator_id=indicator_id,
            current_record_id=db_record.id,
            numeric_value=db_record.numeric_value,
            text_value=db_record.text_value,
            boolean_value=db_record.boolean_value,
            file_path=db_record.file_path,
            recorded_date=recorded_date,
            recorded_by=recorded_by,
            notes=notes,
            is_abnormal=db_record.is_abnormal,
            change_type="insert"
        )
        db.add(history_record)
        db.commit()
        
        return db_record

def get_patient_health_records(
    db: Session,
    patient_id: int,
    category_id: Optional[int] = None,
    indicator_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100
) -> List[PatientHealthRecord]:
    """Get patient health records with optional filters"""
    query = db.query(PatientHealthRecord).filter(
        PatientHealthRecord.patient_id == patient_id
    ).join(HealthIndicator)
    
    if category_id:
        query = query.filter(HealthIndicator.category_id == category_id)
    
    if indicator_id:
        query = query.filter(PatientHealthRecord.indicator_id == indicator_id)
    
    return query.order_by(desc(PatientHealthRecord.recorded_date)).offset(skip).limit(limit).all()

def get_patient_health_record(
    db: Session,
    patient_id: int,
    indicator_id: int
) -> Optional[PatientHealthRecord]:
    """Get the latest health record for a specific patient-indicator combination"""
    return db.query(PatientHealthRecord).filter(
        and_(
            PatientHealthRecord.patient_id == patient_id,
            PatientHealthRecord.indicator_id == indicator_id
        )
    ).first()

def get_patient_health_history(
    db: Session,
    patient_id: int,
    indicator_id: int,
    days: int = 30
) -> List[HealthDataHistory]:
    """Get health data history for a specific patient-indicator combination"""
    start_date = date.today() - timedelta(days=days)
    
    return db.query(HealthDataHistory).filter(
        and_(
            HealthDataHistory.patient_id == patient_id,
            HealthDataHistory.indicator_id == indicator_id,
            HealthDataHistory.recorded_date >= start_date
        )
    ).order_by(desc(HealthDataHistory.recorded_date)).all()

def get_patient_dashboard_data(db: Session, patient_id: int) -> Dict[str, Any]:
    """Get comprehensive dashboard data for a patient"""
    
    # Get all health records for the patient
    health_records = db.query(PatientHealthRecord).filter(
        PatientHealthRecord.patient_id == patient_id
    ).join(HealthIndicator).join(HealthIndicatorCategory).all()
    
    # Group records by category
    dashboard_data = {}
    total_indicators = len(health_records)
    abnormal_count = 0
    
    for record in health_records:
        category_name = record.indicator.category.name
        
        if category_name not in dashboard_data:
            dashboard_data[category_name] = {
                "category_id": record.indicator.category_id,
                "indicators": []
            }
        
        if record.is_abnormal:
            abnormal_count += 1
        
        dashboard_data[category_name]["indicators"].append({
            "indicator_id": record.indicator_id,
            "indicator_name": record.indicator.name,
            "unit": record.indicator.unit,
            "normal_range_min": record.indicator.normal_range_min,
            "normal_range_max": record.indicator.normal_range_max,
            "current_value": {
                "numeric": record.numeric_value,
                "text": record.text_value,
                "boolean": record.boolean_value,
                "file": record.file_path
            },
            "recorded_date": record.recorded_date.isoformat(),
            "is_abnormal": record.is_abnormal,
            "notes": record.notes
        })
    
    # Calculate health score (simple formula: normal indicators / total indicators * 100)
    health_score = ((total_indicators - abnormal_count) / total_indicators * 100) if total_indicators > 0 else 100
    
    return {
        "patient_id": patient_id,
        "total_indicators": total_indicators,
        "abnormal_indicators": abnormal_count,
        "health_score": round(health_score, 1),
        "categories": dashboard_data,
        "last_updated": datetime.utcnow().isoformat()
    }

def update_patient_health_summary(db: Session, patient_id: int) -> PatientHealthSummary:
    """Update or create patient health summary"""
    
    # Get patient's health records
    health_records = db.query(PatientHealthRecord).filter(
        PatientHealthRecord.patient_id == patient_id
    ).all()
    
    total_indicators = len(health_records)
    abnormal_count = sum(1 for record in health_records if record.is_abnormal)
    health_score = ((total_indicators - abnormal_count) / total_indicators * 100) if total_indicators > 0 else 100
    
    # Get or create summary
    summary = db.query(PatientHealthSummary).filter(
        PatientHealthSummary.patient_id == patient_id
    ).first()
    
    if not summary:
        summary = PatientHealthSummary(patient_id=patient_id)
        db.add(summary)
    
    # Update summary
    summary.total_indicators_tracked = total_indicators
    summary.abnormal_indicators_count = abnormal_count
    summary.health_score = health_score
    summary.last_updated = datetime.utcnow()
    summary.updated_at = datetime.utcnow()
    
    # Identify high/medium risk indicators (simplified logic)
    high_risk_ids = [r.indicator_id for r in health_records if r.is_abnormal]
    summary.high_risk_indicators = json.dumps(high_risk_ids)
    
    db.commit()
    db.refresh(summary)
    
    return summary 