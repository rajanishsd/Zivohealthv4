from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import crud
from app.api import deps
from app.db.session import get_db
from app.schemas.timezone import Timezone

router = APIRouter()

@router.get("/", response_model=List[Timezone])
def get_timezones(
    db: Session = Depends(get_db),
    _: bool = Depends(deps.verify_api_key_dependency),
):
    """Get all active timezones."""
    timezones = crud.timezone.get_all(db)
    return timezones
