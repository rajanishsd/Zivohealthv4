from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import Any

from app.api import deps
from app.db.session import get_db
from app.core.auth_service import AuthService
from app.schemas.auth import (
    EmailStartRequest, EmailStartResponse, EmailPasswordRequest,
    EmailOtpRequestRequest, EmailOtpVerifyRequest, GoogleSsoRequest,
    RefreshTokenRequest, AuthResponse, AuthTokensResponse, DeviceInfo
)

router = APIRouter()

def get_device_info(request: Request) -> DeviceInfo:
    """Extract device information from request headers"""
    headers = request.headers
    
    return DeviceInfo(
        device_id=headers.get("X-Device-Id"),
        device_model=headers.get("X-Device-Model"),
        os_version=headers.get("X-OS-Version"),
        app_version=headers.get("X-App-Version"),
        user_agent=headers.get("User-Agent")
    )

def get_client_ip(request: Request) -> str:
    """Extract client IP address from request"""
    # Check for forwarded headers first (when behind proxy)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Fallback to direct connection
    return request.client.host if request.client else "unknown"

@router.post("/email/start", response_model=EmailStartResponse)
def email_start(
    *,
    db: Session = Depends(get_db),
    request: Request,
    email_data: EmailStartRequest,
    _: bool = Depends(deps.verify_api_key_dependency),
) -> Any:
    """
    Check if email exists and return appropriate response.
    This is the first step in the email login flow.
    """
    auth_service = AuthService(db)
    return auth_service.check_email_exists(email_data.email)

@router.post("/email/password", response_model=AuthResponse)
def email_password_login(
    *,
    db: Session = Depends(get_db),
    request: Request,
    login_data: EmailPasswordRequest,
    _: bool = Depends(deps.verify_api_key_dependency),
) -> Any:
    """
    Authenticate user with email and password.
    """
    try:
        auth_service = AuthService(db)
        device_info = get_device_info(request)
        ip_address = get_client_ip(request)
        
        return auth_service.authenticate_with_password(
            email=login_data.email,
            password=login_data.password,
            device_info=device_info,
            ip_address=ip_address
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )

@router.post("/email/otp/request")
def email_otp_request(
    *,
    db: Session = Depends(get_db),
    request: Request,
    otp_data: EmailOtpRequestRequest,
    _: bool = Depends(deps.verify_api_key_dependency),
) -> Any:
    """
    Request OTP for email authentication.
    """
    try:
        auth_service = AuthService(db)
        device_info = get_device_info(request)
        ip_address = get_client_ip(request)
        
        return auth_service.request_otp(
            email=otp_data.email,
            device_info=device_info,
            ip_address=ip_address
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/email/otp/verify", response_model=AuthResponse)
def email_otp_verify(
    *,
    db: Session = Depends(get_db),
    request: Request,
    verify_data: EmailOtpVerifyRequest,
    _: bool = Depends(deps.verify_api_key_dependency),
) -> Any:
    """
    Verify OTP and authenticate user.
    """
    try:
        auth_service = AuthService(db)
        device_info = get_device_info(request)
        ip_address = get_client_ip(request)
        
        return auth_service.verify_otp(
            email=verify_data.email,
            code=verify_data.code,
            device_info=device_info,
            ip_address=ip_address
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )

@router.post("/google/verify", response_model=AuthResponse)
def google_sso_verify(
    *,
    db: Session = Depends(get_db),
    request: Request,
    google_data: GoogleSsoRequest,
    _: bool = Depends(deps.verify_api_key_dependency),
) -> Any:
    """
    Verify Google SSO token and authenticate user.
    """
    try:
        auth_service = AuthService(db)
        device_info = get_device_info(request)
        ip_address = get_client_ip(request)
        
        return auth_service.authenticate_with_google(
            id_token_str=google_data.id_token,
            device_info=device_info,
            ip_address=ip_address
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )

@router.post("/refresh", response_model=AuthTokensResponse)
def refresh_tokens(
    *,
    db: Session = Depends(get_db),
    refresh_data: RefreshTokenRequest,
    _: bool = Depends(deps.verify_api_key_dependency),
) -> Any:
    """
    Refresh access token using refresh token.
    """
    try:
        auth_service = AuthService(db)
        return auth_service.refresh_tokens(refresh_data.refresh_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
