from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api import deps
from app.db.session import get_db
from app.models.user import User
from app.models.user_profile import (
    UserProfile,
    UserLifestyle,
    UserNotificationPreferences,
    UserCondition,
    UserAllergy,
    Condition,
    Allergen,
)


router = APIRouter()


@router.get("/me", response_model=dict)
def get_my_profile(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
    _: bool = Depends(deps.verify_api_key_dependency),
) -> Dict[str, Any]:
    """Return a combined view of the current user's profile details.

    Combines: basic (UserProfile + User.email), conditions, allergies, lifestyle, notifications.
    Consent is intentionally excluded from this endpoint.
    """
    # Basic
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    basic: Dict[str, Any] = {
        "full_name": profile.full_name,
        "date_of_birth": profile.date_of_birth.isoformat() if profile.date_of_birth else None,
        "gender": profile.gender,
        "height_cm": profile.height_cm,
        "weight_kg": profile.weight_kg,
        "body_type": profile.body_type,
        "activity_level": profile.activity_level,
        "timezone": profile.timezone,
        "email": current_user.email,
        "phone_number": profile.phone_number,
    }

    # Conditions
    user_conditions = (
        db.query(UserCondition, Condition)
        .outerjoin(Condition, UserCondition.condition_id == Condition.id)
        .filter(UserCondition.user_id == current_user.id)
        .all()
    )
    condition_names: List[str] = []
    other_condition_text: str | None = None
    for uc, cond in user_conditions:
        if cond and cond.name:
            condition_names.append(cond.name)
        if uc.other_text:
            other_condition_text = uc.other_text

    # Allergies
    user_allergies = (
        db.query(UserAllergy, Allergen)
        .outerjoin(Allergen, UserAllergy.allergen_id == Allergen.id)
        .filter(UserAllergy.user_id == current_user.id)
        .all()
    )
    allergy_names: List[str] = []
    other_allergy_text: str | None = None
    for ua, allergen in user_allergies:
        if allergen and allergen.name:
            allergy_names.append(allergen.name)
        if ua.other_text:
            other_allergy_text = ua.other_text

    conditions: Dict[str, Any] = {
        "condition_names": condition_names,
        "other_condition_text": other_condition_text,
        "allergies": allergy_names,
        "other_allergy_text": other_allergy_text,
    }

    # Lifestyle
    lifestyle_row = db.query(UserLifestyle).filter(UserLifestyle.user_id == current_user.id).first()
    lifestyle: Dict[str, Any] = {
        "smokes": lifestyle_row.smokes if lifestyle_row else False,
        "drinks_alcohol": lifestyle_row.drinks_alcohol if lifestyle_row else False,
        "exercises_regularly": lifestyle_row.exercises_regularly if lifestyle_row else False,
        "exercise_type": lifestyle_row.exercise_type if lifestyle_row else None,
        "exercise_frequency_per_week": lifestyle_row.exercise_frequency_per_week if lifestyle_row else 0,
    }

    # Notifications
    notif = (
        db.query(UserNotificationPreferences)
        .filter(UserNotificationPreferences.user_id == current_user.id)
        .first()
    )
    notifications: Dict[str, Any] = {
        "timezone": notif.timezone if notif else (profile.timezone if profile else "UTC"),
        "window_start_local": notif.window_start_local.isoformat() if notif else "07:00:00",
        "window_end_local": notif.window_end_local.isoformat() if notif else "21:00:00",
        "email_enabled": notif.email_enabled if notif else True,
        "sms_enabled": notif.sms_enabled if notif else False,
        "push_enabled": notif.push_enabled if notif else True,
    }

    return {
        "basic": basic,
        "conditions": conditions,
        "lifestyle": lifestyle,
        "notifications": notifications,
    }


