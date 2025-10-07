from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.timezone import TimezoneDictionary
from app.schemas.timezone import TimezoneBase

class CRUDTimezone:
    def get(self, db: Session, id: int) -> Optional[TimezoneDictionary]:
        return db.query(TimezoneDictionary).filter(TimezoneDictionary.id == id).first()

    def get_all(self, db: Session) -> List[TimezoneDictionary]:
        return db.query(TimezoneDictionary).filter(TimezoneDictionary.is_active == True).order_by(TimezoneDictionary.display_name).all()

    def get_by_identifier(self, db: Session, identifier: str) -> Optional[TimezoneDictionary]:
        return db.query(TimezoneDictionary).filter(TimezoneDictionary.identifier == identifier).first()

# Create instance that can be imported directly
timezone = CRUDTimezone()
