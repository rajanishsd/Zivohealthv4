from datetime import datetime, date
from typing import List, Optional
from pydantic import BaseModel, Field


class MentalHealthEntryBase(BaseModel):
    recorded_at: datetime
    entry_type: str = Field(pattern=r"^(emotion_now|mood_today)$")
    pleasantness_score: int = Field(ge=-3, le=3)
    pleasantness_label: str
    feelings: List[str] = []
    impacts: List[str] = []
    notes: Optional[str] = None


class MentalHealthEntryCreate(MentalHealthEntryBase):
    pass


class MentalHealthEntryResponse(MentalHealthEntryBase):
    id: int
    user_id: int

    class Config:
        from_attributes = True


class MentalHealthDailyPoint(BaseModel):
    date: date
    score: int
    label: str
    feelings: List[str] = []
    impacts: List[str] = []

class NameCount(BaseModel):
    name: str
    count: int


class MentalHealthRollupResponse(BaseModel):
    data_points: List[MentalHealthDailyPoint]
    range: str
    feelings_counts: List[NameCount] = []
    impacts_counts: List[NameCount] = []


