from typing import List
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user_profile import (
    UserProfile,
    Condition,
    Allergen,
    UserCondition,
    UserAllergy,
    UserLifestyle,
    UserNotificationPreferences,
    UserConsent,
    UserMeasurementPreferences,
)
from app.schemas.onboarding import OnboardingPayload


def upsert_catalog_items(db: Session, model, names: List[str]) -> List[int]:
    ids = []
    for name in names:
        item = db.query(model).filter(model.name == name).first()
        if not item:
            item = model(name=name)
            db.add(item)
            db.flush()
        ids.append(item.id)
    return ids


def submit_onboarding(db: Session, user: User, payload: OnboardingPayload, *, ip_address: str, user_agent: str) -> None:
    """Create or update all onboarding-related records in a single transaction."""
    # Ensure email+phone present together
    if not payload.basic.email or not payload.basic.phone_number:
        raise ValueError("Email and phone number are required together")

    # Update user email if provided
    if user.email != payload.basic.email:
        user.email = payload.basic.email
    # Extract name fields for profile
    fn = getattr(payload.basic, 'first_name', None)
    mn = getattr(payload.basic, 'middle_name', None)
    ln = getattr(payload.basic, 'last_name', None)
    if (not fn and not ln) and getattr(payload.basic, 'full_name', None):
        parts = payload.basic.full_name.strip().split()
        if parts:
            fn = parts[0]
            if len(parts) > 1:
                ln = parts[-1]
            if len(parts) > 2:
                mn = " ".join(parts[1:-1])

    # UserProfile upsert
    profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
    if not profile:
        profile = UserProfile(user_id=user.id)
        db.add(profile)

    profile.first_name = fn
    profile.middle_name = mn
    profile.last_name = ln
    profile.date_of_birth = payload.basic.date_of_birth
    profile.gender = payload.basic.gender
    profile.height_cm = payload.basic.height_cm
    profile.weight_kg = payload.basic.weight_kg
    profile.body_type = payload.basic.body_type
    profile.activity_level = payload.basic.activity_level
    profile.phone_number = payload.basic.phone_number
    profile.country_code_id = getattr(payload.basic, 'country_code_id', None)
    profile.timezone = payload.basic.timezone
    profile.timezone_id = getattr(payload.basic, 'timezone_id', None)
    # Mark onboarding as completed when full payload is submitted
    profile.onboarding_status = 'completed'

    # Lifestyle upsert
    lifestyle = db.query(UserLifestyle).filter(UserLifestyle.user_id == user.id).first()
    if not lifestyle:
        lifestyle = UserLifestyle(user_id=user.id)
        db.add(lifestyle)

    lifestyle.smokes = payload.lifestyle.smokes
    lifestyle.drinks_alcohol = payload.lifestyle.drinks_alcohol
    lifestyle.exercises_regularly = payload.lifestyle.exercises_regularly
    lifestyle.exercise_type = payload.lifestyle.exercise_type
    lifestyle.exercise_frequency_per_week = payload.lifestyle.exercise_frequency_per_week

    # Notification prefs upsert
    prefs = db.query(UserNotificationPreferences).filter(UserNotificationPreferences.user_id == user.id).first()
    if not prefs:
        prefs = UserNotificationPreferences(user_id=user.id)
        db.add(prefs)

    prefs.timezone = payload.notifications.timezone
    prefs.window_start_local = payload.notifications.window_start_local
    prefs.window_end_local = payload.notifications.window_end_local
    prefs.email_enabled = payload.notifications.email_enabled
    prefs.sms_enabled = payload.notifications.sms_enabled
    prefs.push_enabled = payload.notifications.push_enabled

    # Catalog upserts and user conditions/allergies
    condition_ids = upsert_catalog_items(db, Condition, payload.conditions.condition_names)
    allergen_ids = upsert_catalog_items(db, Allergen, payload.conditions.allergies)

    # Clear and reinsert user conditions/allergies for simplicity
    db.query(UserCondition).filter(UserCondition.user_id == user.id).delete()
    db.query(UserAllergy).filter(UserAllergy.user_id == user.id).delete()

    for cid in condition_ids:
        db.add(UserCondition(user_id=user.id, condition_id=cid))
    if payload.conditions.other_condition_text:
        db.add(UserCondition(user_id=user.id, other_text=payload.conditions.other_condition_text))

    for aid in allergen_ids:
        db.add(UserAllergy(user_id=user.id, allergen_id=aid))
    if payload.conditions.other_allergy_text:
        db.add(UserAllergy(user_id=user.id, other_text=payload.conditions.other_allergy_text))

    # Consents: append a record for each provided consent
    for c in payload.consents:
        db.add(
            UserConsent(
                user_id=user.id,
                consent_type=c.consent_type,
                consented=c.consented,
                version=c.version,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        )

    db.commit()


