from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.country_code import CountryCodeDictionary


class CRUDCountryCode:
    def get(self, db: Session, id: int) -> Optional[CountryCodeDictionary]:
        return db.query(CountryCodeDictionary).filter(CountryCodeDictionary.id == id).first()

    def get_all(self, db: Session) -> List[CountryCodeDictionary]:
        return (
            db.query(CountryCodeDictionary)
            .filter(CountryCodeDictionary.is_active == True)
            .order_by(CountryCodeDictionary.country_name)
            .all()
        )


country_code = CRUDCountryCode()


