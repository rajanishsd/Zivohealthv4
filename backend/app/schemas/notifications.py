from pydantic import BaseModel


class NotificationSettings(BaseModel):
    notifications_enabled: bool

    class Config:
        from_attributes = True


