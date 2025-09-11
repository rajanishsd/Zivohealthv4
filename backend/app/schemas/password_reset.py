from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


class PasswordResetTokenResponse(BaseModel):
    message: str


class PasswordResetSuccess(BaseModel):
    message: str


class PasswordResetToken(BaseModel):
    id: int
    user_id: int
    token_hash: str
    expires_at: datetime
    used: bool
    created_at: datetime
    used_at: Optional[datetime] = None

    class Config:
        from_attributes = True
