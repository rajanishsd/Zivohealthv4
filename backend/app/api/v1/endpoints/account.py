from datetime import datetime, timedelta
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api import deps
from app.db.session import get_db
from app.models.user import User

router = APIRouter()


@router.post('/schedule-delete', response_model=dict)
def schedule_account_delete(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Mark the current user for deletion and deactivate for 7 days.

    - Sets is_active = False
    - Sets is_tobe_deleted = True
    - Sets delete_date = now + 7 days
    """
    # Re-load the user in the current DB session to avoid cross-session attach errors
    db_user = db.get(User, current_user.id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    db_user.is_active = False
    db_user.is_tobe_deleted = True
    db_user.delete_date = datetime.utcnow() + timedelta(days=7)

    db.commit()
    db.refresh(db_user)
    return {
        'message': 'Account deactivated for 7 days. You can reactivate before the scheduled deletion date.',
        'delete_date': db_user.delete_date.isoformat()
    }


@router.get('/deletion-status', response_model=dict)
def deletion_status(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
    _: bool = Depends(deps.verify_api_key_dependency),
) -> Dict[str, Any]:
    """Return current deletion scheduling status for the logged-in user.

    Note: "wasScheduledForDeletion" cannot be determined server-side without a
    historical audit. This endpoint reports the current state only. The client
    may infer reactivation from the login response (reactivated flag).
    """
    db_user = db.get(User, current_user.id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "isScheduledForDeletion": bool(db_user.is_tobe_deleted),
        "wasScheduledForDeletion": False,
        "deleteDate": db_user.delete_date.isoformat() if db_user.delete_date else None,
    }
