import os
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.password_reset_token import PasswordResetToken
from app.services.email_service import email_service
from app.core.config import settings


class PasswordResetService:
    def __init__(self):
        self.token_expiry_minutes = int(os.getenv("PASSWORD_RESET_TOKEN_EXPIRY_MINUTES", "30"))

    def request_password_reset(self, db: Session, email: str) -> bool:
        """
        Request password reset for a user or doctor
        Returns True if email was sent (even if user/doctor doesn't exist for security)
        """
        try:
            from app.models.doctor import Doctor
            
            # Find user by email first
            user = db.query(User).filter(User.email == email).first()
            doctor = None
            
            if user:
                user_type = "user"
                user_name = user.full_name
                user_id = user.id
                doctor_id = None
            else:
                # If not a user, check if it's a doctor
                doctor = db.query(Doctor).filter(Doctor.email == email).first()
                if doctor:
                    user_type = "doctor"
                    user_name = doctor.full_name
                    user_id = None
                    doctor_id = doctor.id
                else:
                    # Neither user nor doctor exists - return True for security
                    return True

            # Generate reset token
            token = self._generate_reset_token()
            token_hash = self._hash_token(token)
            
            # Set expiration time
            expires_at = datetime.utcnow() + timedelta(minutes=self.token_expiry_minutes)
            
            # Create password reset token record
            reset_token = PasswordResetToken(
                user_id=user_id,
                doctor_id=doctor_id,
                user_type=user_type,
                token_hash=token_hash,
                expires_at=expires_at,
                used=False
            )
            
            db.add(reset_token)
            db.commit()
            
            # Send email
            email_sent = email_service.send_password_reset_email(
                to_email=email,
                reset_token=token,
                user_name=user_name,
                user_type=user_type
            )
            
            if not email_sent:
                # If email failed, remove the token
                db.delete(reset_token)
                db.commit()
                return False
            
            return True
            
        except Exception as e:
            print(f"Error in request_password_reset: {e}")
            db.rollback()
            return False

    def reset_password(self, db: Session, token: str, new_password: str) -> bool:
        """
        Reset password using a valid token (for both users and doctors)
        """
        try:
            from app.models.doctor import Doctor
            from app.core.security import get_password_hash
            
            # Hash the provided token
            token_hash = self._hash_token(token)
            
            # Find valid, unused token
            reset_token = db.query(PasswordResetToken).filter(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.used == False,
                PasswordResetToken.expires_at > datetime.utcnow()
            ).first()
            
            if not reset_token:
                return False
            
            # Update password based on user type
            if reset_token.user_type == "user":
                user = db.query(User).filter(User.id == reset_token.user_id).first()
                if not user:
                    return False
                user.hashed_password = get_password_hash(new_password)
            elif reset_token.user_type == "doctor":
                doctor = db.query(Doctor).filter(Doctor.id == reset_token.doctor_id).first()
                if not doctor:
                    return False
                doctor.hashed_password = get_password_hash(new_password)
            else:
                return False
            
            # Mark token as used
            reset_token.used = True
            reset_token.used_at = datetime.utcnow()
            
            db.commit()
            return True
            
        except Exception as e:
            print(f"Error in reset_password: {e}")
            db.rollback()
            return False

    def verify_reset_token(self, db: Session, token: str) -> bool:
        """
        Verify if a reset token is valid and not expired
        """
        try:
            token_hash = self._hash_token(token)
            
            reset_token = db.query(PasswordResetToken).filter(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.used == False,
                PasswordResetToken.expires_at > datetime.utcnow()
            ).first()
            
            return reset_token is not None
            
        except Exception as e:
            print(f"Error in verify_reset_token: {e}")
            return False

    def _generate_reset_token(self) -> str:
        """Generate a secure random token"""
        return secrets.token_urlsafe(32)

    def _hash_token(self, token: str) -> str:
        """Hash token for storage"""
        return hashlib.sha256(token.encode()).hexdigest()

    def cleanup_expired_tokens(self, db: Session) -> int:
        """
        Clean up expired tokens (can be called periodically)
        Returns number of tokens cleaned up
        """
        try:
            expired_tokens = db.query(PasswordResetToken).filter(
                PasswordResetToken.expires_at < datetime.utcnow()
            ).all()
            
            count = len(expired_tokens)
            for token in expired_tokens:
                db.delete(token)
            
            db.commit()
            return count
            
        except Exception as e:
            print(f"Error in cleanup_expired_tokens: {e}")
            db.rollback()
            return 0


# Create global instance
password_reset_service = PasswordResetService()
