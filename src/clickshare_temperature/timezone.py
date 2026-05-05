from __future__ import annotations
from typing import Literal
import datetime
from zoneinfo import ZoneInfo
import time
import enum

UTC = datetime.timezone.utc
LOCAL_TZ: datetime.tzinfo|NotFoundType|None = None


class _Sentinel(enum.Enum):
    token = enum.auto()

type NotFoundType = Literal[_Sentinel.token]
NotFound: NotFoundType = _Sentinel.token


class TimezoneError(Exception):
    """Custom exception for timezone-related errors."""
    pass

class TimezoneLookupError(TimezoneError):
    """Custom exception for timezone lookup errors."""
    pass


def detect_local_timezone() -> datetime.tzinfo:
    """Detect the local timezone using the tzdata database."""
    def expand_tz_abbr(tz_abbr: str) -> str|None:
        """Expand a timezone abbreviation to a full timezone name if possible."""
        tz_abbr = tz_abbr.upper()
        tz_map = {
            "EST": "US/Eastern",
            "EDT": "US/Eastern",
            "CST": "US/Central",
            "CDT": "US/Central",
            "MST": "US/Mountain",
            "MDT": "US/Mountain",
            "PST": "US/Pacific",
            "PDT": "US/Pacific",
        }
        return tz_map.get(tz_abbr)
    try:
        tz_abbr = time.tzname[time.daylight]
        tz_name = expand_tz_abbr(tz_abbr)
        if tz_name is not None:
            return ZoneInfo(tz_name)
        else:
            raise TimezoneLookupError(f"Could not expand timezone abbreviation '{tz_abbr}' to a full timezone name.")
    except Exception as e:
        raise TimezoneLookupError(f"Failed to detect local timezone: {e}")


def get_local_timezone() -> datetime.tzinfo|NotFoundType:
    """Get the local timezone, detecting it if necessary."""
    global LOCAL_TZ
    if LOCAL_TZ is None:
        try:
            LOCAL_TZ = detect_local_timezone()
        except TimezoneLookupError:
            LOCAL_TZ = NotFound
    return LOCAL_TZ


def is_aware(dt: datetime.datetime) -> bool:
    """Check if a datetime object is timezone-aware."""
    return dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None


def ensure_aware(dt: datetime.datetime) -> datetime.datetime:
    """Ensure a datetime object is timezone-aware"""
    if not is_aware(dt):
        raise TimezoneError("Expected a timezone-aware datetime, but got a naive datetime.")
    return dt


def make_aware(dt: datetime.datetime, tz: datetime.tzinfo) -> datetime.datetime:
    """Make a naive datetime object timezone-aware by assigning the given timezone."""
    if is_aware(dt):
        raise TimezoneError("Expected a naive datetime, but got a timezone-aware datetime.")
    return dt.replace(tzinfo=tz)


def as_timezone(dt: datetime.datetime, tz: datetime.tzinfo) -> datetime.datetime:
    """Convert a datetime object to the given timezone."""
    if not is_aware(dt):
        raise TimezoneError("Expected a timezone-aware datetime, but got a naive datetime.")
    return dt.astimezone(tz)


def localize(dt: datetime.datetime) -> datetime.datetime:
    """Convert a UTC datetime to the local timezone."""
    local_tz = get_local_timezone()
    if local_tz is NotFound:
        raise TimezoneError("Local timezone could not be detected.")
    if not is_aware(dt):
        dt = make_aware(dt, UTC)
    return as_timezone(dt, local_tz)


def normalize(dt: datetime.datetime) -> datetime.datetime:
    """Normalize a datetime to the local timezone, converting it if necessary."""
    local_tz = get_local_timezone()
    if local_tz is NotFound:
        raise TimezoneError("Local timezone could not be detected.")
    if not is_aware(dt):
        raise TimezoneError("Expected a timezone-aware datetime, but got a naive datetime.")
    return as_timezone(dt, local_tz)


def as_utc(dt: datetime.datetime) -> datetime.datetime:
    """Convert a datetime to UTC."""
    if not is_aware(dt):
        raise TimezoneError("Expected a timezone-aware datetime, but got a naive datetime.")
    return as_timezone(dt, UTC)

def utcnow() -> datetime.datetime:
    """Get the current time as a timezone-aware datetime in UTC."""
    return datetime.datetime.now(UTC)
