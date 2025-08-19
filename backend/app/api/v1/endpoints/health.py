from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from datetime import date, datetime

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.crud import health_crud
from app.schemas import health_schemas

router = APIRouter()

# Health Indicator Categories endpoints
@router.get("/categories", response_model=List[health_schemas.HealthIndicatorCategory])
def get_health_categories(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all health indicator categories"""
    categories = health_crud.get_health_categories(db, skip=skip, limit=limit)
    return categories

@router.get("/categories/{category_id}", response_model=health_schemas.HealthIndicatorCategory)
def get_health_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific health indicator category"""
    category = health_crud.get_health_category(db, category_id=category_id)
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Health indicator category not found"
        )
    return category

# Health Indicators endpoints
@router.get("/indicators", response_model=List[health_schemas.HealthIndicatorWithCategory])
def get_health_indicators(
    category_id: Optional[int] = Query(None, description="Filter by category ID"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get health indicators with optional category filter"""
    indicators = health_crud.get_health_indicators(
        db, category_id=category_id, skip=skip, limit=limit
    )
    return indicators

@router.get("/indicators/{indicator_id}", response_model=health_schemas.HealthIndicatorWithCategory)
def get_health_indicator(
    indicator_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific health indicator"""
    indicator = health_crud.get_health_indicator(db, indicator_id=indicator_id)
    if indicator is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Health indicator not found"
        )
    return indicator

# Patient Health Records endpoints
@router.post("/records", response_model=health_schemas.PatientHealthRecord)
def create_health_record(
    record_data: health_schemas.PatientHealthRecordCreate,
    patient_id: Optional[int] = Query(None, description="Patient ID (if different from current user)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create or update a patient health record"""
    
    # Use provided patient_id or current user's ID
    target_patient_id = patient_id if patient_id else current_user.id
    
    # Validate that the indicator exists
    indicator = health_crud.get_health_indicator(db, indicator_id=record_data.indicator_id)
    if not indicator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Health indicator not found"
        )
    
    # Prepare value data based on indicator type
    value_data = {}
    if indicator.data_type == "numeric" and record_data.numeric_value is not None:
        value_data["numeric_value"] = record_data.numeric_value
    elif indicator.data_type == "text" and record_data.text_value is not None:
        value_data["text_value"] = record_data.text_value
    elif indicator.data_type == "boolean" and record_data.boolean_value is not None:
        value_data["boolean_value"] = record_data.boolean_value
    elif indicator.data_type == "file" and record_data.file_path is not None:
        value_data["file_path"] = record_data.file_path
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid value type for indicator. Expected: {indicator.data_type}"
        )
    
    try:
        health_record = health_crud.create_patient_health_record(
            db=db,
            patient_id=target_patient_id,
            indicator_id=record_data.indicator_id,
            value_data=value_data,
            recorded_date=record_data.recorded_date,
            recorded_by=current_user.id,
            notes=record_data.notes
        )
        
        # Update patient health summary
        health_crud.update_patient_health_summary(db, target_patient_id)
        
        return health_record
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating health record: {str(e)}"
        )

@router.get("/records", response_model=List[health_schemas.PatientHealthRecordWithIndicator])
def get_patient_health_records(
    patient_id: Optional[int] = Query(None, description="Patient ID (if different from current user)"),
    category_id: Optional[int] = Query(None, description="Filter by category ID"),
    indicator_id: Optional[int] = Query(None, description="Filter by indicator ID"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get patient health records with optional filters"""
    
    # Use provided patient_id or current user's ID
    target_patient_id = patient_id if patient_id else current_user.id
    
    records = health_crud.get_patient_health_records(
        db=db,
        patient_id=target_patient_id,
        category_id=category_id,
        indicator_id=indicator_id,
        skip=skip,
        limit=limit
    )
    return records

@router.get("/records/{indicator_id}", response_model=health_schemas.PatientHealthRecordWithIndicator)
def get_patient_health_record(
    indicator_id: int,
    patient_id: Optional[int] = Query(None, description="Patient ID (if different from current user)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the latest health record for a specific indicator"""
    
    # Use provided patient_id or current user's ID
    target_patient_id = patient_id if patient_id else current_user.id
    
    record = health_crud.get_patient_health_record(
        db=db,
        patient_id=target_patient_id,
        indicator_id=indicator_id
    )
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Health record not found"
        )
    return record

@router.get("/history/{indicator_id}", response_model=List[health_schemas.HealthDataHistory])
def get_health_data_history(
    indicator_id: int,
    patient_id: Optional[int] = Query(None, description="Patient ID (if different from current user)"),
    days: int = Query(30, description="Number of days of history to retrieve"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get health data history for a specific indicator"""
    
    # Use provided patient_id or current user's ID
    target_patient_id = patient_id if patient_id else current_user.id
    
    history = health_crud.get_patient_health_history(
        db=db,
        patient_id=target_patient_id,
        indicator_id=indicator_id,
        days=days
    )
    return history

@router.get("/dashboard", response_model=health_schemas.PatientDashboard)
def get_patient_dashboard(
    patient_id: Optional[int] = Query(None, description="Patient ID (if different from current user)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get comprehensive dashboard data for a patient"""
    
    # Use provided patient_id or current user's ID
    target_patient_id = patient_id if patient_id else current_user.id
    
    dashboard_data = health_crud.get_patient_dashboard_data(db=db, patient_id=target_patient_id)
    return dashboard_data

@router.get("/summary", response_model=health_schemas.PatientHealthSummary)
def get_patient_health_summary(
    patient_id: Optional[int] = Query(None, description="Patient ID (if different from current user)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get or create patient health summary"""
    
    # Use provided patient_id or current user's ID
    target_patient_id = patient_id if patient_id else current_user.id
    
    summary = health_crud.update_patient_health_summary(db=db, patient_id=target_patient_id)
    return summary

# Bulk data operations
@router.post("/records/bulk", response_model=health_schemas.BulkHealthDataResponse)
def create_bulk_health_records(
    bulk_data: health_schemas.BulkHealthDataCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create multiple health records in bulk"""
    
    created_count = 0
    updated_count = 0
    errors = []
    records = []
    
    for data_entry in bulk_data.data:
        try:
            indicator_id = data_entry.get("indicator_id")
            if not indicator_id:
                errors.append("Missing indicator_id in data entry")
                continue
            
            # Validate indicator exists
            indicator = health_crud.get_health_indicator(db, indicator_id=indicator_id)
            if not indicator:
                errors.append(f"Health indicator {indicator_id} not found")
                continue
            
            # Prepare value data based on indicator type
            value_data = {}
            if indicator.data_type == "numeric" and "numeric_value" in data_entry:
                value_data["numeric_value"] = data_entry["numeric_value"]
            elif indicator.data_type == "text" and "text_value" in data_entry:
                value_data["text_value"] = data_entry["text_value"]
            elif indicator.data_type == "boolean" and "boolean_value" in data_entry:
                value_data["boolean_value"] = data_entry["boolean_value"]
            elif indicator.data_type == "file" and "file_path" in data_entry:
                value_data["file_path"] = data_entry["file_path"]
            
            if not value_data:
                errors.append(f"No valid value provided for indicator {indicator_id}")
                continue
            
            # Check if record exists to determine if it's create or update
            existing_record = health_crud.get_patient_health_record(
                db=db,
                patient_id=bulk_data.patient_id,
                indicator_id=indicator_id
            )
            
            health_record = health_crud.create_patient_health_record(
                db=db,
                patient_id=bulk_data.patient_id,
                indicator_id=indicator_id,
                value_data=value_data,
                recorded_date=bulk_data.recorded_date,
                recorded_by=bulk_data.recorded_by or current_user.id,
                notes=data_entry.get("notes")
            )
            
            records.append(health_record)
            
            if existing_record:
                updated_count += 1
            else:
                created_count += 1
                
        except Exception as e:
            errors.append(f"Error processing indicator {data_entry.get('indicator_id', 'unknown')}: {str(e)}")
    
    # Update patient health summary
    try:
        health_crud.update_patient_health_summary(db, bulk_data.patient_id)
    except Exception as e:
        errors.append(f"Error updating patient summary: {str(e)}")
    
    return health_schemas.BulkHealthDataResponse(
        created_count=created_count,
        updated_count=updated_count,
        errors=errors,
        records=records
    ) 