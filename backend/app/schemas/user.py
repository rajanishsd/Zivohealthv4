from typing import Optional
from pydantic import BaseModel, EmailStr
from datetime import datetime
from app.schemas.timezone import Timezone

class UserBase(BaseModel):
    email: EmailStr
    # Deprecated: kept for backward-compat request bodies; not used for storage
    full_name: Optional[str] = None
    # timezone now lives on user profile

class UserCreate(UserBase):
    password: str

class UserCreateGoogle(UserBase):
    password: Optional[str] = None

class UserUpdate(UserBase):
    password: Optional[str] = None

class UserInDBBase(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    # timezone relation removed from User

    class Config:
        from_attributes = True

class User(UserInDBBase):
    pass

class UserInDB(UserInDBBase):
    hashed_password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenPayload(BaseModel):
    sub: Optional[int] = None
    is_doctor: Optional[bool] = False 
    is_admin: Optional[bool] = False