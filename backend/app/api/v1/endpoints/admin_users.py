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
        result.append({
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "is_active": u.is_active,
            "is_tobe_deleted": u.is_tobe_deleted,
            "delete_date": u.delete_date.isoformat() if u.delete_date else None,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "updated_at": u.updated_at.isoformat() if u.updated_at else None,
        })
    return result


@router.post("/users/delete", response_model=Dict[str, Any])
def bulk_delete_users(
    *,
    db: Session = Depends(get_db),
    _: Any = Depends(deps.get_current_active_admin),
    body: Dict[str, List[int]] = Body(..., embed=True),
) -> Dict[str, Any]:
    """
    Admin-only: Mark one or more users for deletion immediately.

    For safety, we mirror the schedule-delete semantics: set is_active=False,
    is_tobe_deleted=True, and delete_date=now (immediate). Hard deletion of
    related data can be handled by a separate maintenance job if needed.
    """
    from datetime import datetime

    user_ids = body.get("user_ids") or []
    if not isinstance(user_ids, list) or any(not isinstance(i, int) for i in user_ids):
        raise HTTPException(status_code=400, detail="Invalid user_ids list")

    if not user_ids:
        return {"updated": 0}

    # Update users in bulk
    updated = 0
    now = datetime.utcnow()
    users = db.query(User).filter(User.id.in_(user_ids)).all()
    for u in users:
        u.is_active = False
        u.is_tobe_deleted = True
        u.delete_date = now
        updated += 1
    db.commit()

    return {"updated": updated}


