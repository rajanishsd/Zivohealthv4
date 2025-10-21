from fastapi import APIRouter, Depends, HTTPException, status, Request, Body
from sqlalchemy.orm import Session
from typing import Any
from datetime import timedelta
import secrets
import string

from app.api import deps
from app.db.session import get_db
from app import crud
from app.core import security
from app.core.config import settings
from app.services.email_service import email_service
from app.core.redis import redis_client

router = APIRouter()


def get_client_ip(request: Request) -> str:
    """Extract client IP address from request"""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    return request.client.host if request.client else "unknown"


def generate_otp(length: int = 6) -> str:
    """Generate a random numeric OTP"""
    return ''.join(secrets.choice(string.digits) for _ in range(length))


def generate_reset_token(length: int = 32) -> str:
    """Generate a secure random token for password reset"""
    return secrets.token_urlsafe(length)


@router.post("/admin/otp/request")
def admin_otp_request(
    *,
    db: Session = Depends(get_db),
    request: Request,
    payload: dict = Body(...),
    _: bool = Depends(deps.verify_api_key_dependency),
) -> Any:
    """
    Request OTP for admin email authentication.
    Sends a 6-digit OTP to the admin's email.
    """
    email = payload.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is required"
        )
    
    # Check if admin exists
    admin = crud.admin.get_by_email(db, email=email)
    if not admin:
        # For security, don't reveal if admin exists
        return {
            "message": "If this email is registered as an admin, an OTP has been sent."
        }
    
    if not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin account is not active"
        )
    
    # Generate OTP
    otp = generate_otp()
    
    # Store OTP in Redis with 10 minute expiration
    redis_key = f"admin_otp:{email}"
    redis_client.setex(redis_key, 600, otp)  # 10 minutes
    
    # Log IP for security
    ip_address = get_client_ip(request)
    print(f"🔐 Admin OTP requested for {email} from IP {ip_address}")
    
    # Send OTP via email
    try:
        email_sent = email_service.send_admin_otp_email(email, otp)
        if not email_sent:
            # Clean up the OTP from Redis if email failed
            redis_client.delete(redis_key)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send OTP email. Please try again later."
            )
    except Exception as e:
        redis_client.delete(redis_key)
        print(f"❌ Failed to send admin OTP email to {email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send OTP email. Please check your email configuration."
        )
    
    return {
        "message": "OTP has been sent to your email address.",
        "expires_in": 600  # seconds
    }


@router.post("/admin/otp/verify", response_model=dict)
def admin_otp_verify(
    *,
    db: Session = Depends(get_db),
    request: Request,
    payload: dict = Body(...),
    _: bool = Depends(deps.verify_api_key_dependency),
) -> Any:
    """
    Verify OTP and authenticate admin.
    Returns admin JWT token on successful verification.
    """
    email = payload.get("email")
    code = payload.get("code")
    
    if not email or not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email and code are required"
        )
    
    # Get stored OTP from Redis
    redis_key = f"admin_otp:{email}"
    stored_otp = redis_client.get(redis_key)
    
    if not stored_otp:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OTP has expired or is invalid"
        )
    
    # Verify OTP
    if stored_otp != code:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid OTP code"
        )
    
    # Get admin
    admin = crud.admin.get_by_email(db, email=email)
    if not admin:
        # Delete OTP for security
        redis_client.delete(redis_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin not found"
        )
    
    if not admin.is_active:
        redis_client.delete(redis_key)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin account is not active"
        )
    
    # Delete used OTP
    redis_client.delete(redis_key)
    
    # Log successful authentication
    ip_address = get_client_ip(request)
    print(f"✅ Admin OTP verified for {email} from IP {ip_address}")
    
    # Generate JWT token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = security.create_access_token(
        admin.id,
        expires_delta=access_token_expires,
        is_admin=True
    )
    
    # Compose admin full name
    admin_parts = [
        p for p in [admin.first_name, admin.middle_name, admin.last_name] if p
    ]
    admin_full_name = " ".join(admin_parts) if admin_parts else None
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "admin": {
            "id": admin.id,
            "email": admin.email,
            "full_name": admin_full_name,
            "is_superadmin": admin.is_superadmin
        }
    }


@router.post("/admin/password/forgot")
def admin_forgot_password(
    *,
    db: Session = Depends(get_db),
    request: Request,
    payload: dict = Body(...),
    _: bool = Depends(deps.verify_api_key_dependency),
) -> Any:
    """
    Request password reset for an admin account.
    Sends a password reset link to the admin's email.
    """
    email = payload.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is required"
        )
    
    # Check if admin exists
    admin = crud.admin.get_by_email(db, email=email)
    
    # For security, always return success message
    success_message = "If this email is registered as an admin, a password reset link has been sent."
    
    if not admin or not admin.is_active:
        # Still return success for security
        return {"message": success_message}
    
    # Generate reset token
    reset_token = generate_reset_token()
    
    # Store token in Redis with 1 hour expiration
    redis_key = f"admin_reset:{reset_token}"
    redis_client.setex(redis_key, 3600, admin.id)  # 1 hour
    
    # Log IP for security
    ip_address = get_client_ip(request)
    print(f"🔐 Admin password reset requested for {email} from IP {ip_address}")
    
    # Build reset URL - use dashboard URL (port 3000 for development)
    # For admin resets, we need the dashboard frontend, not the user-facing frontend
    dashboard_url = settings.FRONTEND_URL.replace(':8000', ':3000') if ':8000' in settings.FRONTEND_URL else settings.FRONTEND_URL
    reset_url = f"{dashboard_url}?token={reset_token}"
    
    # Send reset email
    try:
        email_sent = email_service.send_admin_password_reset_email(
            email, reset_url, admin.first_name
        )
        if not email_sent:
            redis_client.delete(redis_key)
            print(f"⚠️ Failed to send password reset email to admin {email}")
    except Exception as e:
        redis_client.delete(redis_key)
        print(f"❌ Error sending password reset email to admin {email}: {e}")
    
    return {"message": success_message}


@router.post("/admin/password/reset")
def admin_reset_password(
    *,
    db: Session = Depends(get_db),
    request: Request,
    payload: dict = Body(...),
    _: bool = Depends(deps.verify_api_key_dependency),
) -> Any:
    """
    Reset admin password using a valid reset token.
    """
    token = payload.get("token")
    new_password = payload.get("new_password")
    
    if not token or not new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token and new password are required"
        )
    
    if len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long"
        )
    
    # Get admin ID from Redis
    redis_key = f"admin_reset:{token}"
    admin_id = redis_client.get(redis_key)
    
    if not admin_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    # Get admin
    admin = crud.admin.get(db, admin_id=int(admin_id))
    if not admin:
        redis_client.delete(redis_key)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin not found"
        )
    
    # Update password
    hashed_password = security.get_password_hash(new_password)
    admin.hashed_password = hashed_password
    db.commit()
    
    # Delete used token
    redis_client.delete(redis_key)
    
    # Log success
    ip_address = get_client_ip(request)
    print(f"✅ Admin password reset successful for {admin.email} from IP {ip_address}")
    
    return {
        "message": "Password has been reset successfully. You can now login with your new password."
    }


@router.get("/admin/password/verify-token/{token}")
def verify_admin_reset_token(
    *,
    db: Session = Depends(get_db),
    token: str,
) -> dict:
    """
    Verify if an admin reset token is valid and not expired.
    """
    redis_key = f"admin_reset:{token}"
    admin_id = redis_client.get(redis_key)
    
    is_valid = admin_id is not None
    
    return {
        "valid": is_valid,
        "message": "Token is valid" if is_valid else "Token is invalid or expired"
    }

