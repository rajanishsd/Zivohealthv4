from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api import deps
from app.schemas.password_reset import (
    PasswordResetRequest,
    PasswordResetConfirm,
    PasswordResetTokenResponse,
    PasswordResetSuccess
)
from app.services.password_reset_service import password_reset_service

router = APIRouter()


@router.post("/forgot-password", response_model=PasswordResetTokenResponse)
def forgot_password(
    *,
    db: Session = Depends(deps.get_db),
    request: PasswordResetRequest,
) -> PasswordResetTokenResponse:
    """
    Request password reset for a user.
    Always returns success message for security (doesn't reveal if user exists).
    """
    try:
        success = password_reset_service.request_password_reset(db, request.email)
        
        if success:
            return PasswordResetTokenResponse(
                message="If this email exists, a password reset link has been sent."
            )
        else:
            # Still return success message for security
            return PasswordResetTokenResponse(
                message="If this email exists, a password reset link has been sent."
            )
            
    except Exception as e:
        # Always return success message for security
        return PasswordResetTokenResponse(
            message="If this email exists, a password reset link has been sent."
        )


@router.post("/reset-password", response_model=PasswordResetSuccess)
def reset_password(
    *,
    db: Session = Depends(deps.get_db),
    request: PasswordResetConfirm,
) -> PasswordResetSuccess:
    """
    Reset password using a valid reset token.
    """
    try:
        success = password_reset_service.reset_password(
            db, request.token, request.new_password
        )
        
        if success:
            return PasswordResetSuccess(
                message="Password has been reset successfully."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token."
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while resetting the password."
        )


@router.get("/verify-reset-token/{token}")
def verify_reset_token(
    *,
    db: Session = Depends(deps.get_db),
    token: str,
) -> dict:
    """
    Verify if a reset token is valid and not expired.
    """
    try:
        is_valid = password_reset_service.verify_reset_token(db, token)
        
        return {
            "valid": is_valid,
            "message": "Token is valid" if is_valid else "Token is invalid or expired"
        }
        
    except Exception as e:
        return {
            "valid": False,
            "message": "Error verifying token"
        }
