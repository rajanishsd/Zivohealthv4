from datetime import timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app import crud
from app.api import deps
from app.core import security
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import User as UserSchema, UserCreate, Token

router = APIRouter()

@router.post("/register", response_model=UserSchema)
def register(
    *,
    db: Session = Depends(deps.get_db),
    user_in: UserCreate,
    _: bool = Depends(deps.verify_api_key_dependency),
) -> Any:
    """
    Create new user.
    """
    user = crud.user.get_by_email(db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="A user with this email already exists.",
        )
    user = crud.user.create(db, obj_in=user_in)
    return user

@router.post("/login", response_model=dict)
async def login(
    db: Session = Depends(deps.get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
    _: bool = Depends(deps.verify_api_key_dependency),
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests.
    Supports both users and doctors.
    """
    # Try to authenticate as a user first
    user = crud.user.authenticate(
        db, email=form_data.username, password=form_data.password
    )
    
    if user and user.is_active:
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        refresh_token_expires = timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
        return {
            "access_token": security.create_access_token(
                user.id, expires_delta=access_token_expires
            ),
            "refresh_token": security.create_refresh_token(
                user.id, expires_delta=refresh_token_expires
            ),
            "token_type": "bearer",
            "user_type": "user",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60  # Convert minutes to seconds
        }
    
    # Try to authenticate as a doctor
    doctor = crud.doctor.authenticate(
        db, email=form_data.username, password=form_data.password
    )
    
    if doctor and doctor.is_active:
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        refresh_token_expires = timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
        return {
            "access_token": security.create_access_token(
                doctor.id, expires_delta=access_token_expires, is_doctor=True
            ),
            "refresh_token": security.create_refresh_token(
                doctor.id, expires_delta=refresh_token_expires, is_doctor=True
            ),
            "token_type": "bearer",
            "user_type": "doctor",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60  # Convert minutes to seconds
        }
    
    # Neither user nor doctor authentication succeeded
    raise HTTPException(status_code=400, detail="Incorrect email or password")

from fastapi import Body

@router.post("/refresh", response_model=dict)
async def refresh_token(
    *,
    db: Session = Depends(deps.get_db),
    refresh_token: str = Body(..., embed=True)
) -> Any:
    """Refresh access token using a refresh token"""
    from jose import jwt
    from jose.exceptions import JWTError
    try:
        payload = jwt.decode(
            refresh_token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token type")
        subject = payload.get("sub")
        is_doctor = payload.get("is_doctor", False)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid refresh token")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": security.create_access_token(
            subject, expires_delta=access_token_expires, is_doctor=is_doctor
        ),
        "token_type": "bearer",
        "user_type": "doctor" if is_doctor else "user",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }

@router.get("/me", response_model=UserSchema)
def read_users_me(
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get current user.
    """
    return current_user 