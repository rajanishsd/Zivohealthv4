from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api import deps
from app.db.session import get_db
from app.schemas.onboarding import OnboardingPayload
from app.crud.onboarding import submit_onboarding
from app.models.user_profile import UserProfile

router = APIRouter()


@router.post("/submit", status_code=204)
def submit(
    *,
    db: Session = Depends(get_db),
    request: Request,
    payload: OnboardingPayload,
    current_user = Depends(deps.get_current_active_user),
    _: bool = Depends(deps.verify_api_key_dependency),
):
    """Submit full onboarding in a single transaction.
    Requires both email and phone; will upsert profile, lifestyle, notifications, conditions/allergies, and consents.
    """
    try:
        ip_address = request.headers.get("X-Real-IP") or request.client.host if request.client else "unknown"
        user_agent = request.headers.get("User-Agent")
        submit_onboarding(db, current_user, payload, ip_address=ip_address, user_agent=user_agent or "")
        return
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/status", response_model=dict)
def get_status(
    db: Session = Depends(get_db),
    current_user = Depends(deps.get_current_active_user),
    _: bool = Depends(deps.verify_api_key_dependency),
):
    """Return onboarding status for current user.
    completed: bool (true if onboarding_status == 'completed' or profile exists with full_name)
    status: string value of onboarding_status
    """
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    status = profile.onboarding_status if profile else None
    completed = False
    if profile:
        if status == 'completed':
            completed = True
        elif (profile.full_name or '').strip():
            completed = True
    return {"completed": completed, "status": status}

