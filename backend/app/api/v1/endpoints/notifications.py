from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api import deps
from app.models.user import User
from app.schemas.notifications import NotificationSettings


router = APIRouter()


@router.get("/settings", response_model=NotificationSettings)
def get_notification_settings(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    return NotificationSettings(notifications_enabled=current_user.notifications_enabled)


@router.put("/settings", response_model=NotificationSettings)
def update_notification_settings(
    payload: NotificationSettings,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    current_user.notifications_enabled = payload.notifications_enabled
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return NotificationSettings(notifications_enabled=current_user.notifications_enabled)


