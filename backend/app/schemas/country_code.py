from datetime import datetime
from pydantic import BaseModel


class CountryCodeBase(BaseModel):
    country_name: str
    iso2: str
    dial_code: str
    min_digits: int
    max_digits: int
    is_active: bool = True


class CountryCode(CountryCodeBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


