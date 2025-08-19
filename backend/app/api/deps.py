from typing import Generator, Union

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.core import security
from app.core.config import settings
from app.db.session import SessionLocal

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login"
)


def get_db() -> Generator:
    try:
        db = SessionLocal()
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        try:
            db.close()
        except Exception:
            pass


def get_current_user(
    db: Session = Depends(get_db), token: str = Depends(reusable_oauth2)
) -> models.User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = schemas.TokenPayload(**payload)
    except (jwt.JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    user = crud.user.get(db, id=token_data.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def get_current_doctor(
    db: Session = Depends(get_db), token: str = Depends(reusable_oauth2)
) -> models.Doctor:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        # Check if this is a doctor token
        if not payload.get("is_doctor", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Doctor access required",
            )
        doctor_id = payload.get("sub")
    except (jwt.JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    doctor = crud.doctor.get(db, doctor_id=int(doctor_id))
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return doctor


def get_current_active_user(
    current_user: models.User = Depends(get_current_user),
) -> models.User:
    if not crud.user.is_active(current_user):
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def get_current_active_doctor(
    current_doctor: models.Doctor = Depends(get_current_doctor),
) -> models.Doctor:
    if not current_doctor.is_active:
        raise HTTPException(status_code=400, detail="Inactive doctor")
    return current_doctor


def get_current_active_superuser(
    current_user: models.User = Depends(get_current_user),
) -> models.User:
    if not crud.user.is_superuser(current_user):
        raise HTTPException(
            status_code=400, detail="The user doesn't have enough privileges"
        )
    return current_user 