from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app import crud
from app.api import deps
from app.schemas.country_code import CountryCode
from app.db.session import get_db


router = APIRouter()


@router.get("/", response_model=List[CountryCode])
def get_all_country_codes(
    db: Session = Depends(get_db),
    _: bool = Depends(deps.verify_api_key_dependency),
) -> List[CountryCode]:
    return crud.country_code.get_all(db)


