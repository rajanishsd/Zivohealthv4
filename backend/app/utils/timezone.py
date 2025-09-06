from datetime import datetime, date, timezone as dt_timezone
from typing import Optional

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

from app.core.config import settings
from sqlalchemy.sql import text, func


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


def to_utc_naive(dt: datetime | None) -> datetime | None:
    """
    Normalize any datetime to UTC-naive (tzinfo=None) for consistent storage/comparison.
    - Aware datetimes are converted to UTC and tzinfo is stripped
    - Naive datetimes are returned as-is (assumed UTC)
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    try:
        return dt.astimezone(dt_timezone.utc).replace(tzinfo=None)
    except Exception:
        # Fallback: drop tzinfo if conversion fails
        return dt.replace(tzinfo=None)


def to_utc_aware(dt: datetime | None) -> datetime | None:
    """
    Normalize any datetime to UTC-aware (tzinfo=UTC) for APIs needing tz-aware values.
    - Aware datetimes are converted to UTC
    - Naive datetimes are assumed UTC and tz attached
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=dt_timezone.utc)
    return dt.astimezone(dt_timezone.utc)


def to_local_naive(dt: datetime | None) -> datetime | None:
    """
    Convert any datetime to local timezone (settings.DEFAULT_TIMEZONE) and strip tzinfo.
    - Aware datetimes are converted to local tz and tzinfo is stripped
    - Naive datetimes are assumed local and returned as-is
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    tz = get_zoneinfo()
    if tz is None:
        # Fallback: convert to UTC then strip
        return dt.astimezone(dt_timezone.utc).replace(tzinfo=None)
    try:
        return dt.astimezone(tz).replace(tzinfo=None)
    except Exception:
        return dt.replace(tzinfo=None)


def local_now_db_expr():
    """
    SQLAlchemy server_default expression for current time in local timezone (timestamp without tz).
    Uses PostgreSQL timezone('<tz>', now()).
    """
    tz_name = getattr(settings, "DEFAULT_TIMEZONE", "UTC")
    return text(f"timezone('{tz_name}', now())")


def local_now_db_func():
    """
    SQLAlchemy func expression for current time in local timezone, for use in UPDATE statements.
    """
    tz_name = getattr(settings, "DEFAULT_TIMEZONE", "UTC")
    return func.timezone(tz_name, func.now())