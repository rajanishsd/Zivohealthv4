from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api import deps
from app.db.session import get_db
from app.models.user import User
from app.schemas.devices import UserDeviceRead, DeviceConnectionUpdate, DevicesConfigResponse
from app.crud import devices as devices_crud
from app.core.config import settings


router = APIRouter()


@router.get("/", response_model=List[UserDeviceRead])
def list_devices(
    *, db: Session = Depends(get_db), current_user: User = Depends(deps.get_current_user)
):
    return devices_crud.list_user_devices(db, user_id=current_user.id)


@router.get("/{provider}/status", response_model=UserDeviceRead)
def get_device_status(
    *,
    provider: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
):
    device = devices_crud.get_or_create_user_device(db, user_id=current_user.id, provider=provider)
    return device


@router.put("/{provider}/status", response_model=UserDeviceRead)
def update_device_status(
    *,
    provider: str,
    update: DeviceConnectionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
):
    device = devices_crud.set_device_connection(
        db, user_id=current_user.id, provider=provider, is_connected=update.is_connected
    )
    return device


@router.get("/config", response_model=DevicesConfigResponse)
def devices_config():
    return DevicesConfigResponse(healthkit_enabled=settings.HEALTHKIT_ENABLED)


