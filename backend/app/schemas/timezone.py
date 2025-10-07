from typing import Optional
from pydantic import BaseModel
from datetime import datetime

class TimezoneBase(BaseModel):
    identifier: str
    display_name: str
    utc_offset: str
    is_active: bool = True

class TimezoneCreate(TimezoneBase):
    pass

class TimezoneUpdate(TimezoneBase):
    pass

class TimezoneInDBBase(TimezoneBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class Timezone(TimezoneInDBBase):
    pass

class TimezoneInDB(TimezoneInDBBase):
    pass
