from typing import List, Optional, Literal
from datetime import date, time
from pydantic import BaseModel, EmailStr, Field


GenderEnum = Literal["male", "female", "other"]
BodyTypeEnum = Literal["ectomorph", "mesomorph", "endomorph"]
ActivityLevelEnum = Literal["sedentary", "lightly_active", "moderately_active", "very_active", "super_active"]
ExerciseTypeEnum = Literal["gym", "running", "yoga", "other"]


class BasicDetails(BaseModel):
    full_name: Optional[str]
    date_of_birth: date
    gender: GenderEnum
    height_cm: Optional[int] = Field(ge=30, le=300)
    weight_kg: Optional[int] = Field(ge=10, le=400)
    body_type: Optional[BodyTypeEnum]
    activity_level: Optional[ActivityLevelEnum]
    timezone: str
    email: EmailStr
    phone_number: str = Field(..., min_length=6, max_length=32)


class HealthConditions(BaseModel):
    condition_names: List[str] = []  # names from catalog
    other_condition_text: Optional[str]
    allergies: List[str] = []        # names from allergen catalog
    other_allergy_text: Optional[str]


class LifestyleHabits(BaseModel):
    smokes: bool
    drinks_alcohol: bool
    exercises_regularly: bool
    exercise_type: Optional[ExerciseTypeEnum]
    exercise_frequency_per_week: Optional[int] = Field(ge=0, le=14)


class NotificationPreferences(BaseModel):
    timezone: str
    window_start_local: time
    window_end_local: time
    email_enabled: Optional[bool] = True
    sms_enabled: Optional[bool] = False
    push_enabled: Optional[bool] = True


class ConsentRecord(BaseModel):
    consent_type: Literal["data_storage", "recommendations", "terms_privacy"]
    consented: bool
    version: Optional[str]


class OnboardingPayload(BaseModel):
    """Full onboarding data submitted in a single transaction."""
    basic: BasicDetails
    conditions: HealthConditions
    lifestyle: LifestyleHabits
    notifications: NotificationPreferences
    consents: List[ConsentRecord]


