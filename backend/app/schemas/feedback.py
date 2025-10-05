from typing import Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime


class FeedbackUploadURLRequest(BaseModel):
    contentType: str = Field(..., pattern=r"^image/(jpeg|png)$")


class FeedbackUploadURLResponse(BaseModel):
    uploadUrl: str
    s3Key: str


class FeedbackCreate(BaseModel):
    s3_key: str
    category: Optional[str] = None
    description: Optional[str] = None
    route: Optional[str] = None
    app_version: Optional[str] = None
    build_number: Optional[str] = None
    platform: Optional[str] = None
    os_version: Optional[str] = None
    device_model: Optional[str] = None
    app_identifier: Optional[str] = None
    status: Optional[str] = "open"
    extra: Optional[dict[str, Any]] = None


class FeedbackUpdate(BaseModel):
    status: Optional[str] = None
    closed_date: Optional[datetime] = None


class Feedback(BaseModel):
    id: str
    user_id: Optional[int]
    submitter_role: Optional[str] = None  # "user" or "doctor"
    submitter_name: Optional[str] = None
    s3_key: str
    category: Optional[str]
    description: Optional[str]
    route: Optional[str]
    app_version: Optional[str]
    build_number: Optional[str]
    platform: Optional[str]
    os_version: Optional[str]
    device_model: Optional[str]
    app_identifier: Optional[str]
    status: str
    closed_date: Optional[datetime] = None
    extra: Optional[dict[str, Any]]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


