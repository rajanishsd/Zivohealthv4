from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, EmailStr, Field

# Request schemas
class EmailStartRequest(BaseModel):
    email: EmailStr

class EmailStartResponse(BaseModel):
    exists: bool
    message: str

class EmailPasswordRequest(BaseModel):
    email: EmailStr
    password: str

class EmailOtpRequestRequest(BaseModel):
    email: EmailStr

class EmailOtpVerifyRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)

class GoogleSsoRequest(BaseModel):
    id_token: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class EmailRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)

class EmailRegisterResponse(BaseModel):
    message: str
    email: str
    verification_required: bool = True

class EmailVerifyRequest(BaseModel):
    token: str

class EmailVerifyResponse(BaseModel):
    message: str
    email: str
    verified: bool

# Device information for login events
class DeviceInfo(BaseModel):
    device_id: Optional[str] = None
    device_model: Optional[str] = None
    os_version: Optional[str] = None
    app_version: Optional[str] = None
    user_agent: Optional[str] = None

# Response schemas
class AuthTokensResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_type: str = "user"
    expires_in: int

class UserInfo(BaseModel):
    id: int
    email: str
    # Kept for compatibility; composed from split fields server-side
    full_name: Optional[str] = None
    email_verified: bool
    last_login_at: Optional[datetime] = None

class AuthResponse(BaseModel):
    tokens: AuthTokensResponse
    user: UserInfo

# Login event schemas
class LoginEventCreate(BaseModel):
    user_id: Optional[int] = None
    method: Literal["email_password", "email_otp", "google"]
    device_id: Optional[str] = None
    device_model: Optional[str] = None
    os_version: Optional[str] = None
    app_version: Optional[str] = None
    ip_address: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    user_agent: Optional[str] = None
    success: bool = True
    error_code: Optional[str] = None

class LoginEventResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    occurred_at: datetime
    method: str
    device_id: Optional[str] = None
    device_model: Optional[str] = None
    os_version: Optional[str] = None
    app_version: Optional[str] = None
    ip_address: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    user_agent: Optional[str] = None
    success: bool
    error_code: Optional[str] = None

    class Config:
        from_attributes = True
