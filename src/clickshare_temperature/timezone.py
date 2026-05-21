from __future__ import annotations
from typing import Literal
import os
import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import time
import enum

from dotenv import load_dotenv

UTC = datetime.timezone.utc
LOCAL_TZ: datetime.tzinfo|NotFoundType|None = None
LOCAL_TZ_ENV_VAR = "CLICKSHARE_LOCAL_TIMEZONE"


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
    """Detect the local timezone using the tzdata database

    Returns:
        The local timezone as a :class:`datetime.tzinfo`.

    Raises:
        TimezoneLookupError: If the local timezone could not be detected.
    """
    load_dotenv()
    local_tz_name = os.getenv(LOCAL_TZ_ENV_VAR)
    if local_tz_name is not None:
        return timezone_from_name(local_tz_name)
    tz_abbr = time.tzname[time.daylight]
    return timezone_from_name(tz_abbr)


def timezone_from_name(tz_name: str) -> datetime.tzinfo:
    """Get a timezone object from a timezone name, with some handling for common abbreviations

    Arguments:
        tz_name: The name of the timezone (e.g. "America/New_York" or "EST")

    Returns:
        A timezone object corresponding to the given name.

    Raises:
        TimezoneLookupError: If the timezone could not be found by name or abbreviation.
    """
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
        tz = ZoneInfo(tz_name)
        return tz
    except ZoneInfoNotFoundError as outer_exc:
        tz_name_expanded = expand_tz_abbr(tz_name)
        if tz_name_expanded is None:
            raise TimezoneLookupError(
                f"Timezone '{tz_name}' not found and could not be expanded from abbreviation."
            ) from outer_exc
        try:
            tz = ZoneInfo(tz_name_expanded)
            return tz
        except ZoneInfoNotFoundError as inner_exc:
            raise TimezoneLookupError(
                f"Timezone '{tz_name}' not found, and expanded name '{tz_name_expanded}' also not found."
            ) from inner_exc


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
