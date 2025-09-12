import secrets
import hashlib
import redis
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from google.auth.transport import requests
from google.oauth2 import id_token

from app.core.config import settings
from app.core import security
from app.models.user import User
from app.models.user_identity import UserIdentity
from app.models.login_event import LoginEvent
from app.schemas.auth import (
    EmailStartResponse, AuthResponse, AuthTokensResponse, 
    UserInfo, LoginEventCreate, DeviceInfo
)
from app.schemas.user import UserCreateGoogle
from app.crud import user as user_crud
from app.services.email_service import EmailService


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True
        )
        self.email_service = EmailService()

    def check_email_exists(self, email: str) -> EmailStartResponse:
        """Check if email exists and return appropriate response"""
        user = user_crud.get_by_email(self.db, email=email)
        return EmailStartResponse(
            exists=user is not None,
            message="Email found" if user else "Email not found"
        )

    def authenticate_with_password(self, email: str, password: str, device_info: DeviceInfo, 
                                 ip_address: Optional[str] = None) -> AuthResponse:
        """Authenticate user with email and password"""
        user = user_crud.authenticate(self.db, email=email, password=password)
        
        if not user or not user.is_active:
            self._log_login_event(
                user_id=None,
                method="email_password",
                device_info=device_info,
                ip_address=ip_address,
                success=False,
                error_code="invalid_credentials"
            )
            raise ValueError("Invalid email or password")

        # Update last login
        user.last_login_at = datetime.utcnow()
        self.db.commit()

        # Create tokens
        tokens = self._create_tokens(user.id, is_doctor=False)
        
        # Log successful login
        self._log_login_event(
            user_id=user.id,
            method="email_password",
            device_info=device_info,
            ip_address=ip_address,
            success=True
        )

        return AuthResponse(
            tokens=tokens,
            user=self._create_user_info(user)
        )

    def request_otp(self, email: str, device_info: DeviceInfo, 
                   ip_address: Optional[str] = None) -> Dict[str, str]:
        """Request OTP for email authentication"""
        # Check rate limiting
        if not self._check_otp_rate_limit(email):
            raise ValueError("Too many OTP requests. Please try again later.")

        # Generate OTP
        otp = self._generate_otp()
        otp_hash = self._hash_otp(otp)
        
        # Store in Redis with TTL
        redis_key = f"otp:{email}"
        self.redis_client.setex(redis_key, settings.OTP_EXPIRY_MINUTES * 60, otp_hash)
        
        # Send OTP via email
        self.email_service.send_otp_email(email, otp)
        
        # Log OTP request
        self._log_login_event(
            user_id=None,
            method="email_otp",
            device_info=device_info,
            ip_address=ip_address,
            success=True
        )

        return {"message": "OTP sent to your email"}

    def verify_otp(self, email: str, code: str, device_info: DeviceInfo,
                  ip_address: Optional[str] = None) -> AuthResponse:
        """Verify OTP and authenticate user"""
        # Check OTP
        if not self._verify_otp(email, code):
            self._log_login_event(
                user_id=None,
                method="email_otp",
                device_info=device_info,
                ip_address=ip_address,
                success=False,
                error_code="invalid_otp"
            )
            raise ValueError("Invalid or expired OTP")

        # Get or create user
        user = user_crud.get_by_email(self.db, email=email)
        if not user:
            # Create new user for OTP verification
            user = self._create_user_from_email(email)
        
        # Update email verification and last login
        user.email_verified_at = datetime.utcnow()
        user.last_login_at = datetime.utcnow()
        self.db.commit()

        # Create or update identity
        self._ensure_email_identity(user, email)

        # Create tokens
        tokens = self._create_tokens(user.id, is_doctor=False)
        
        # Log successful login
        self._log_login_event(
            user_id=user.id,
            method="email_otp",
            device_info=device_info,
            ip_address=ip_address,
            success=True
        )

        return AuthResponse(
            tokens=tokens,
            user=self._create_user_info(user)
        )

    def authenticate_with_google(self, id_token_str: str, device_info: DeviceInfo,
                               ip_address: Optional[str] = None) -> AuthResponse:
        """Authenticate user with Google SSO"""
        try:
            # Verify Google ID token using iOS client ID
            # For mobile apps, we use the iOS client ID for verification
            # The mobile app uses PKCE, so no client secret is needed
            idinfo = id_token.verify_oauth2_token(
                id_token_str, 
                requests.Request(), 
                settings.GOOGLE_CLIENT_ID  # This is the iOS client ID
            )
            
            google_sub = idinfo.get('sub')
            email = idinfo.get('email')
            email_verified = idinfo.get('email_verified', False)
            name = idinfo.get('name')
            
            if not email or not google_sub:
                raise ValueError("Invalid Google token")
                
        except Exception as e:
            self._log_login_event(
                user_id=None,
                method="google",
                device_info=device_info,
                ip_address=ip_address,
                success=False,
                error_code="invalid_google_token"
            )
            raise ValueError("Invalid Google token")

        # Find or create user
        user = self._find_or_create_google_user(email, google_sub, name, email_verified)
        
        # Update last login
        user.last_login_at = datetime.utcnow()
        self.db.commit()

        # Create tokens
        tokens = self._create_tokens(user.id, is_doctor=False)
        
        # Log successful login
        self._log_login_event(
            user_id=user.id,
            method="google",
            device_info=device_info,
            ip_address=ip_address,
            success=True
        )

        return AuthResponse(
            tokens=tokens,
            user=self._create_user_info(user)
        )

    def refresh_tokens(self, refresh_token: str) -> AuthTokensResponse:
        """Refresh access token using refresh token"""
        try:
            payload = jwt.decode(
                refresh_token, 
                settings.SECRET_KEY, 
                algorithms=[security.ALGORITHM]
            )
            if payload.get("type") != "refresh":
                raise ValueError("Invalid token type")
            
            user_id = payload.get("sub")
            is_doctor = payload.get("is_doctor", False)
            
        except JWTError:
            raise ValueError("Invalid refresh token")

        # Create new access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = security.create_access_token(
            user_id, 
            expires_delta=access_token_expires, 
            is_doctor=is_doctor
        )

        return AuthTokensResponse(
            access_token=access_token,
            refresh_token=refresh_token,  # Keep same refresh token
            token_type="bearer",
            user_type="doctor" if is_doctor else "user",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

    def _generate_otp(self) -> str:
        """Generate a random OTP"""
        return ''.join([str(secrets.randbelow(10)) for _ in range(settings.OTP_LENGTH)])

    def _hash_otp(self, otp: str) -> str:
        """Hash OTP for secure storage"""
        return hashlib.sha256(otp.encode()).hexdigest()

    def _verify_otp(self, email: str, code: str) -> bool:
        """Verify OTP code"""
        redis_key = f"otp:{email}"
        stored_hash = self.redis_client.get(redis_key)
        
        if not stored_hash:
            return False
            
        code_hash = self._hash_otp(code)
        if stored_hash == code_hash:
            # Remove OTP after successful verification
            self.redis_client.delete(redis_key)
            return True
            
        return False

    def _check_otp_rate_limit(self, email: str) -> bool:
        """Check if email is within OTP rate limit"""
        rate_key = f"otp_rate:{email}:{datetime.utcnow().strftime('%Y-%m-%d')}"
        current_count = self.redis_client.get(rate_key)
        
        if current_count and int(current_count) >= settings.OTP_RATE_LIMIT_PER_EMAIL:
            return False
            
        # Increment counter
        self.redis_client.incr(rate_key)
        self.redis_client.expire(rate_key, 86400)  # 24 hours
        return True

    def _create_tokens(self, user_id: int, is_doctor: bool = False) -> AuthTokensResponse:
        """Create access and refresh tokens"""
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        refresh_token_expires = timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
        
        return AuthTokensResponse(
            access_token=security.create_access_token(
                user_id, 
                expires_delta=access_token_expires, 
                is_doctor=is_doctor
            ),
            refresh_token=security.create_refresh_token(
                user_id, 
                expires_delta=refresh_token_expires, 
                is_doctor=is_doctor
            ),
            token_type="bearer",
            user_type="doctor" if is_doctor else "user",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

    def _create_user_info(self, user: User) -> UserInfo:
        """Create user info response"""
        return UserInfo(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            email_verified=user.email_verified_at is not None,
            last_login_at=user.last_login_at
        )

    def _create_user_from_email(self, email: str) -> User:
        """Create new user from email (for OTP signup)"""
        user_data = {
            "email": email,
            "hashed_password": None,  # No password for OTP users
            "is_active": True
        }
        return user_crud.create(self.db, obj_in=user_data)

    def _find_or_create_google_user(self, email: str, google_sub: str, 
                                  name: Optional[str], email_verified: bool) -> User:
        """Find existing user or create new one for Google SSO"""
        # Try to find by Google identity first
        identity = self.db.query(UserIdentity).filter(
            UserIdentity.provider == "google",
            UserIdentity.provider_subject == google_sub
        ).first()
        
        if identity:
            return identity.user
        
        # Try to find by email and link Google identity
        user = user_crud.get_by_email(self.db, email=email)
        if user:
            # Link Google identity to existing user
            self._ensure_google_identity(user, google_sub, email, email_verified)
            return user
        
        # Create new user
        user_data = UserCreateGoogle(
            email=email,
            full_name=name,
            password=None  # Google users don't have passwords
        )
        user = user_crud.create_google_user(self.db, obj_in=user_data)
        
        # Set email verification status for Google users
        if email_verified:
            user.email_verified_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(user)
        
        # Create Google identity
        self._ensure_google_identity(user, google_sub, email, email_verified)
        
        return user

    def _ensure_email_identity(self, user: User, email: str):
        """Ensure user has email identity"""
        identity = self.db.query(UserIdentity).filter(
            UserIdentity.user_id == user.id,
            UserIdentity.provider == "email",
            UserIdentity.email == email
        ).first()
        
        if not identity:
            identity = UserIdentity(
                user_id=user.id,
                provider="email",
                provider_subject=email,
                email=email,
                email_verified=True
            )
            self.db.add(identity)
            self.db.commit()

    def _ensure_google_identity(self, user: User, google_sub: str, email: str, email_verified: bool):
        """Ensure user has Google identity"""
        identity = self.db.query(UserIdentity).filter(
            UserIdentity.user_id == user.id,
            UserIdentity.provider == "google",
            UserIdentity.provider_subject == google_sub
        ).first()
        
        if not identity:
            identity = UserIdentity(
                user_id=user.id,
                provider="google",
                provider_subject=google_sub,
                email=email,
                email_verified=email_verified
            )
            self.db.add(identity)
            self.db.commit()

    def _log_login_event(self, user_id: Optional[int], method: str, device_info: DeviceInfo,
                        ip_address: Optional[str] = None, success: bool = True, 
                        error_code: Optional[str] = None):
        """Log login event for audit"""
        # Get geo location from IP (simplified - you might want to use a proper GeoIP service)
        country, region, city = self._get_location_from_ip(ip_address)
        
        login_event = LoginEvent(
            user_id=user_id,
            method=method,
            device_id=device_info.device_id,
            device_model=device_info.device_model,
            os_version=device_info.os_version,
            app_version=device_info.app_version,
            ip_address=ip_address,
            country=country,
            region=region,
            city=city,
            user_agent=device_info.user_agent,
            success=success,
            error_code=error_code
        )
        
        self.db.add(login_event)
        self.db.commit()

    def _get_location_from_ip(self, ip_address: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Get location from IP address (simplified implementation)"""
        # This is a placeholder - you should implement proper GeoIP lookup
        # For now, return None values
        return None, None, None
