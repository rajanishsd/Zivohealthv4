from datetime import datetime, date
from typing import Optional

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

from app.core.config import settings


def get_zoneinfo() -> Optional["ZoneInfo"]:
    tz_name = getattr(settings, "DEFAULT_TIMEZONE", None)
    if not tz_name or not ZoneInfo:
        return None
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return None


def now_local() -> datetime:
    tz = get_zoneinfo()
    return datetime.now(tz) if tz else datetime.utcnow()


def today_local() -> date:
    return now_local().date()


def isoformat_now() -> str:
    return now_local().isoformat()


