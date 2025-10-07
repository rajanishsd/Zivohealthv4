from datetime import datetime
from typing import Optional, Any, Dict, List
from pydantic import BaseModel


class UserDeviceBase(BaseModel):
    provider: str
    device_name: str
    is_connected: bool


class UserDeviceRead(UserDeviceBase):
    id: int
    connected_at: Optional[datetime] = None
    disconnected_at: Optional[datetime] = None
    device_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DeviceConnectionUpdate(BaseModel):
    is_connected: bool


class DevicesConfigResponse(BaseModel):
    healthkit_enabled: bool


