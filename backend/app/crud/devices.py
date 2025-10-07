from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.user_device import UserDevice


DEFAULT_DEVICE_NAMES = {
    "healthkit": "Apple HealthKit",
}


def get_or_create_user_device(
    db: Session, *, user_id: int, provider: str, device_name: Optional[str] = None
) -> UserDevice:
    device = (
        db.query(UserDevice)
        .filter(and_(UserDevice.user_id == user_id, UserDevice.provider == provider))
        .first()
    )
    if device:
        return device
    device = UserDevice(
        user_id=user_id,
        provider=provider,
        device_name=device_name or DEFAULT_DEVICE_NAMES.get(provider, provider.title()),
        is_connected=False,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


def list_user_devices(db: Session, *, user_id: int) -> List[UserDevice]:
    return db.query(UserDevice).filter(UserDevice.user_id == user_id).all()


def set_device_connection(
    db: Session, *, user_id: int, provider: str, is_connected: bool
) -> UserDevice:
    device = get_or_create_user_device(db, user_id=user_id, provider=provider)
    now = datetime.utcnow()
    device.is_connected = is_connected
    if is_connected:
        device.connected_at = now
    else:
        device.disconnected_at = now
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


