from datetime import datetime, timedelta
from typing import Any, Union
from jose import jwt
from passlib.context import CryptContext
from app.core.config import settings
from app.utils.timezone import now_local
import hashlib
import hmac

# Export the algorithm constant for use in other modules
ALGORITHM = settings.ALGORITHM

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_access_token(subject: Union[str, Any], expires_delta: timedelta = None, is_doctor: bool = False) -> str:
    if expires_delta:
        expire = now_local() + expires_delta
    else:
        expire = now_local() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {"exp": expire, "sub": str(subject), "is_doctor": is_doctor}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_refresh_token(subject: Union[str, Any], expires_delta: timedelta = None, is_doctor: bool = False) -> str:
    if expires_delta:
        expire = now_local() + expires_delta
    else:
        expire = now_local() + timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {"exp": expire, "sub": str(subject), "is_doctor": is_doctor, "type": "refresh"}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_api_key(api_key: str) -> bool:
    """
    Verify API key against configured valid keys
    """
    if not hasattr(settings, 'VALID_API_KEYS'):
        return False
    
    valid_keys = settings.VALID_API_KEYS
    if isinstance(valid_keys, str):
        valid_keys = [valid_keys]
    
    return api_key in valid_keys

def generate_app_signature(payload: str, timestamp: str, app_secret: str) -> str:
    """
    Generate HMAC signature for app authentication
    """
    message = f"{payload}.{timestamp}"
    signature = hmac.new(
        app_secret.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return signature

def verify_app_signature(payload: str, timestamp: str, signature: str, app_secret: str) -> bool:
    """
    Verify HMAC signature for app authentication
    """
    expected_signature = generate_app_signature(payload, timestamp, app_secret)
    return hmac.compare_digest(signature, expected_signature)