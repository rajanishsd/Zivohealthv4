from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Body, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.db.session import get_db
from app.models.user import User


router = APIRouter()


@router.get("/users", response_model=List[Dict[str, Any]])
def list_users(
    *,
    db: Session = Depends(get_db),
    _: Any = Depends(deps.get_current_active_admin),
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
) -> List[Dict[str, Any]]:
    """Admin-only: List users with basic fields for dashboard display."""
    users = db.query(User).offset(skip).limit(limit).all()
    result: List[Dict[str, Any]] = []
    for u in users:
        # Get name fields from user profile if it exists
        first_name = None
        middle_name = None
        last_name = None
        full_name = None
        
        if hasattr(u, 'profile') and u.profile:
            # Handle case where profile might be a list (multiple profiles) or single object
            profile = u.profile[0] if isinstance(u.profile, list) and len(u.profile) > 0 else u.profile
            if profile:
                first_name = profile.first_name
                middle_name = profile.middle_name
                last_name = profile.last_name
            parts = [p for p in [first_name, middle_name, last_name] if p]
            full_name = " ".join(parts) if parts else None
        
        result.append({
            "id": u.id,
            "email": u.email,
            "first_name": first_name,
            "middle_name": middle_name,
            "last_name": last_name,
            "full_name": full_name,
            "is_active": u.is_active,
            "is_tobe_deleted": u.is_tobe_deleted,
            "delete_date": u.delete_date.isoformat() if u.delete_date else None,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "updated_at": u.updated_at.isoformat() if u.updated_at else None,
        })
    return result


@router.post("/users/mark-for-deletion", response_model=Dict[str, Any])
def mark_users_for_deletion(
    *,
    db: Session = Depends(get_db),
    _: Any = Depends(deps.get_current_active_admin),
    body: Dict[str, List[int]] = Body(...),
) -> Dict[str, Any]:
    """
    Admin-only: Mark one or more users for deletion (soft delete).
    
    This deactivates the account but preserves all data:
    - Sets is_active=False (user cannot log in)
    - Sets is_tobe_deleted=True (marked for deletion)
    - Sets delete_date=now
    
    All user data remains in the database for compliance or recovery.
    Use /users/delete-permanently for hard deletion.
    """
    from datetime import datetime

    user_ids = body.get("user_ids") or []
    if not isinstance(user_ids, list) or any(not isinstance(i, int) for i in user_ids):
        raise HTTPException(status_code=400, detail="Invalid user_ids list")

    if not user_ids:
        return {"updated": 0}

    # Update users in bulk (soft delete)
    updated = 0
    now = datetime.utcnow()
    users = db.query(User).filter(User.id.in_(user_ids)).all()
    for u in users:
        u.is_active = False
        u.is_tobe_deleted = True
        u.delete_date = now
        updated += 1
    db.commit()

    return {"updated": updated, "message": f"Marked {updated} user(s) for deletion"}


@router.post("/users/delete-permanently", response_model=Dict[str, Any])
def delete_users_permanently(
    *,
    db: Session = Depends(get_db),
    _: Any = Depends(deps.get_current_active_admin),
    body: Dict[str, List[int]] = Body(...),
) -> Dict[str, Any]:
    """
    Admin-only: PERMANENTLY DELETE users and all associated data (hard delete).
    
    ⚠️ WARNING: This action is IRREVERSIBLE!
    
    This will delete:
    - User account and profile
    - All health data (nutrition, vitals, lab reports)
    - All chat sessions and messages
    - All appointments and prescriptions
    - All related records across all tables
    
    Relies on database CASCADE constraints to automatically delete all related data.
    Run migration: alembic upgrade head (includes 067_fix_cascade_delete_constraints)
    
    Use with extreme caution. Consider using /users/mark-for-deletion instead.
    """

    user_ids = body.get("user_ids") or []
    if not isinstance(user_ids, list) or any(not isinstance(i, int) for i in user_ids):
        raise HTTPException(status_code=400, detail="Invalid user_ids list")

    if not user_ids:
        return {"deleted": 0}

    deleted = 0
    errors = []
    
    for user_id in user_ids:
        try:
            # Verify user exists using raw SQL (avoid loading into session)
            from sqlalchemy import text
            result = db.execute(text("SELECT EXISTS(SELECT 1 FROM users WHERE id = :user_id)"), {"user_id": user_id})
            user_exists = result.scalar()
            
            if not user_exists:
                errors.append(f"User {user_id} not found")
                continue
            
            # Delete using raw SQL to bypass SQLAlchemy ORM relationship handling
            # This lets the database CASCADE constraints do their job properly
            # 
            # CASCADE constraints automatically delete ALL related data (50 tables):
            #
            # Raw Data: vitals_raw_data, nutrition_raw_data
            # Categorized: vitals_raw_categorized, lab_report_categorized
            #
            # Hourly Aggregates: vitals_hourly_aggregates
            # Daily Aggregates: vitals_daily_aggregates, nutrition_daily_aggregates, 
            #                   mental_health_daily, lab_reports_daily
            # Weekly Aggregates: vitals_weekly_aggregates, nutrition_weekly_aggregates
            # Monthly Aggregates: vitals_monthly_aggregates, nutrition_monthly_aggregates, 
            #                     lab_reports_monthly
            # Quarterly/Yearly: lab_reports_quarterly, lab_reports_yearly
            #
            # Goals & Planning: nutrition_goals, user_nutrient_focus
            # Sync Status: vitals_sync_status, nutrition_sync_status
            #
            # Clinical: clinical_notes, clinical_reports, medical_images, lab_reports
            # Chat: chat_sessions, chat_messages, agent_memory
            # Appointments: appointments, consultation_requests (+ prescriptions via cascade)
            #
            # User Profile: user_profiles, user_conditions, user_allergies, user_lifestyle,
            #               user_consents, user_measurement_preferences, user_notification_preferences
            # Health: patient_health_records, health_data_history, patient_health_summaries,
            #         mental_health_entries, health_score_calculations_log, health_score_results_daily
            # Auth: user_identities, login_events, password_reset_tokens
            # Devices: user_devices
            # Pharmacy: pharmacy_medications, pharmacy_bills
            # Logs: document_processing_logs, opentelemetry_traces
            #
            # ⚠️ REQUIRES migration 067_fix_cascade_delete_constraints to be applied!
            
            # Use raw SQL to avoid ORM trying to handle relationships
            # (ORM would try to SET NULL on relationships before deletion)
            db.execute(text("DELETE FROM users WHERE id = :user_id"), {"user_id": user_id})
            db.commit()
            deleted += 1
            
        except Exception as e:
            db.rollback()
            errors.append(f"Failed to delete user {user_id}: {str(e)}")
            continue
    
    result = {
        "deleted": deleted,
        "message": f"Permanently deleted {deleted} user(s) and all associated data"
    }
    
    if errors:
        result["errors"] = errors
    
    return result


# Backwards compatibility: redirect old endpoint to new one
@router.post("/users/delete", response_model=Dict[str, Any])
def bulk_delete_users_legacy(
    *,
    db: Session = Depends(get_db),
    admin: Any = Depends(deps.get_current_active_admin),
    body: Dict[str, List[int]] = Body(...),
) -> Dict[str, Any]:
    """
    Legacy endpoint for backwards compatibility.
    
    This endpoint now redirects to /users/mark-for-deletion (soft delete).
    Consider updating your client to use the new endpoints:
    - /users/mark-for-deletion for soft delete
    - /users/delete-permanently for hard delete
    """
    return mark_users_for_deletion(db=db, _=admin, body=body)


