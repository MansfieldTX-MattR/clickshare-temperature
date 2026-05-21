from __future__ import annotations
from typing import Literal, overload
import os
import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import time
import enum

from dotenv import load_dotenv

UTC = datetime.timezone.utc
LOCAL_TZ: datetime.tzinfo|NotFoundType|None = None
LOCAL_TZ_ENV_VAR = "CLICKSHARE_LOCAL_TIMEZONE"
"""Environment variable name for specifying the local timezone name"""


class _Sentinel(enum.Enum):
    token = enum.auto()

type NotFoundType = Literal[_Sentinel.token]
"""Type for a sentinel value indicating that something was not found"""
NotFound: NotFoundType = _Sentinel.token
"""Sentinel value indicating that something was not found"""


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


@overload
def get_local_timezone(raise_exc: Literal[False] = ...) -> datetime.tzinfo|NotFoundType: ...
@overload
def get_local_timezone(raise_exc: Literal[True] = ...) -> datetime.tzinfo: ...
def get_local_timezone(raise_exc: bool = False) -> datetime.tzinfo|NotFoundType:
    """Get the local timezone, detecting it if necessary

    Arguments:
        raise_exc: If True, raise an exception if the local timezone cannot be detected.

    Returns:
        The local timezone as a :class:`datetime.tzinfo`, or :obj:`NotFound` if
            the timezone could not be detected (and *raise_exc* is False).

    Raises:
        TimezoneLookupError: If the local timezone could not be detected and *raise_exc* is True.
    """
    global LOCAL_TZ
    if LOCAL_TZ is None:
        try:
            LOCAL_TZ = detect_local_timezone()
        except TimezoneLookupError:
            LOCAL_TZ = NotFound
    if raise_exc and LOCAL_TZ is NotFound:
        raise TimezoneLookupError("Local timezone could not be detected.")
    return LOCAL_TZ


def set_local_timezone(tz_or_name: datetime.tzinfo|str) -> None:
    """Set the local timezone from a timezone object or a timezone name

    Arguments:
        tz_or_name: A timezone object or a timezone name (e.g. "America/New_York" or "EST")

    Raises:
        TimezoneLookupError: If a timezone name is provided but the timezone
            cannot be found.
    """
    global LOCAL_TZ
    if isinstance(tz_or_name, str):
        tz = timezone_from_name(tz_or_name)
    else:
        tz = tz_or_name
    LOCAL_TZ = tz


def is_aware(dt: datetime.datetime) -> bool:
    """Check if a datetime object is timezone-aware."""
    return dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None


def ensure_aware(dt: datetime.datetime) -> datetime.datetime:
    """Ensure a datetime object is timezone-aware

    Arguments:
        dt: A datetime object.

    Returns:
        The same datetime object if it is timezone-aware.

    Raises:
        TimezoneError: If the input datetime is not timezone-aware.
    """
    if not is_aware(dt):
        raise TimezoneError("Expected a timezone-aware datetime, but got a naive datetime.")
    return dt


def make_aware(dt: datetime.datetime, tz: datetime.tzinfo) -> datetime.datetime:
    """Make a naive datetime object timezone-aware by assigning the given timezone

    Arguments:
        dt: A naive datetime object
        tz: The timezone to assign to the datetime object

    Returns:
        A timezone-aware datetime object.

    Raises:
        TimezoneError: If the input datetime is not naive
    """
    if is_aware(dt):
        raise TimezoneError("Expected a naive datetime, but got a timezone-aware datetime.")
    return dt.replace(tzinfo=tz)


def as_timezone(dt: datetime.datetime, tz: datetime.tzinfo) -> datetime.datetime:
    """Convert a datetime object to the given timezone

    Arguments:
        dt: A timezone-aware datetime object.
        tz: The timezone to convert the datetime to.

    Returns:
        A timezone-aware datetime object in the given timezone.

    Raises:
        TimezoneError: If the input datetime is not timezone-aware.
    """
    if not is_aware(dt):
        raise TimezoneError("Expected a timezone-aware datetime, but got a naive datetime.")
    return dt.astimezone(tz)


def localize(dt: datetime.datetime) -> datetime.datetime:
    """Convert a UTC datetime to the local timezone

    Arguments:
        dt: A timezone-aware datetime in UTC.

    Returns:
        A timezone-aware datetime in the local timezone.

    Raises:
        TimezoneLookupError: If the local timezone could not be detected.
        TimezoneError: If the input datetime is not timezone-aware.
    """
    local_tz = get_local_timezone(raise_exc=True)
    if not is_aware(dt):
        dt = make_aware(dt, UTC)
    return as_timezone(dt, local_tz)


def normalize(dt: datetime.datetime) -> datetime.datetime:
    """Normalize a datetime to the local timezone, converting it if necessary

    Arguments:
        dt: A timezone-aware datetime.

    Returns:
        A timezone-aware datetime in the local timezone.

    Raises:
        TimezoneLookupError: If the local timezone could not be detected.
        TimezoneError: If the input datetime is not timezone-aware.
    """
    local_tz = get_local_timezone()
    if local_tz is NotFound:
        raise TimezoneError("Local timezone could not be detected.")
    if not is_aware(dt):
        raise TimezoneError("Expected a timezone-aware datetime, but got a naive datetime.")
    return as_timezone(dt, local_tz)


def as_utc(dt: datetime.datetime) -> datetime.datetime:
    """Convert a datetime to UTC

    Arguments:
        dt: A timezone-aware datetime.

    Raises:
        TimezoneError: If the input datetime is not timezone-aware.
    """
    if not is_aware(dt):
        raise TimezoneError("Expected a timezone-aware datetime, but got a naive datetime.")
    return as_timezone(dt, UTC)

def utcnow() -> datetime.datetime:
    """Get the current time as a timezone-aware datetime in UTC."""
    return datetime.datetime.now(UTC)
