from __future__ import annotations
from typing import Literal, Sequence, NamedTuple, TypedDict, NotRequired, TYPE_CHECKING
import datetime

if TYPE_CHECKING:
    from ssl import SSLContext
    from aiohttp import BasicAuth, BaseConnector
    from aiohttp.client_reqrep import Fingerprint
    from aiohttp.client_middlewares import ClientMiddlewareType
    from aiohttp.typedefs import LooseCookies, LooseHeaders, StrOrURL


class AuthInfo(NamedTuple):
    """Authentication information for the BaseUnit API."""
    username: str
    password: str


class BaseUnitInfoSerializeTD(TypedDict):
    """TypedDict for serializing BaseUnitInfo to JSON
    """
    ip_address: str
    hostname: str
    room_name: str


class BaseUnitInfo(NamedTuple):
    """Information about a ClickShare BaseUnit
    """
    ip_address: str
    """IP address of the BaseUnit"""
    hostname: str
    """Hostname of the BaseUnit"""
    room_name: str
    """Name of the meeting room the BaseUnit is located in"""

    def serialize(self) -> BaseUnitInfoSerializeTD:
        """Serialize the :class:`BaseUnitInfo` to a dictionary for JSON serialization
        """
        return {
            "ip_address": self.ip_address,
            "hostname": self.hostname,
            "room_name": self.room_name,
        }

    @classmethod
    def deserialize(cls, data: BaseUnitInfoSerializeTD) -> BaseUnitInfo:
        """Deserialize a dictionary into a :class:`BaseUnitInfo` object
        """
        return cls(
            ip_address=data["ip_address"],
            hostname=data["hostname"],
            room_name=data["room_name"],
        )

type BaseUnitStatusErrorCode = Literal["Ok", "Warning", "Error"]

class BaseUnitStatusSerializeTD(TypedDict):
    """TypedDict for serializing BaseUnitStatus to JSON"""
    base_unit: BaseUnitInfoSerializeTD
    current_uptime_seconds: int
    total_uptime_seconds: int
    error_code: BaseUnitStatusErrorCode
    error_message: str | None
    first_used: str
    in_use: bool
    sharing: bool

class BaseUnitStatus(NamedTuple):
    base_unit: BaseUnitInfo
    """The BaseUnit this status is for"""
    current_uptime: datetime.timedelta
    """Current uptime of the BaseUnit"""
    total_uptime: datetime.timedelta
    """Total uptime of the BaseUnit"""
    error_code: BaseUnitStatusErrorCode
    """Error code indicating the status of the BaseUnit"""
    error_message: str | None
    """Error message if the error code is not "Ok" """
    first_used: datetime.datetime
    """Timestamp of when the BaseUnit was first used"""
    in_use: bool
    """Whether the BaseUnit is currently in use"""
    sharing: bool
    """Whether the BaseUnit is currently sharing"""

    def serialize(self) -> BaseUnitStatusSerializeTD:
        """Serialize the :class:`BaseUnitStatus` to a dictionary for JSON serialization"""
        return {
            "base_unit": self.base_unit.serialize(),
            "current_uptime_seconds": int(self.current_uptime.total_seconds()),
            "total_uptime_seconds": int(self.total_uptime.total_seconds()),
            "error_code": self.error_code,
            "error_message": self.error_message,
            "first_used": self.first_used.isoformat(),
            "in_use": self.in_use,
            "sharing": self.sharing,
        }

    @classmethod
    def deserialize(cls, data: BaseUnitStatusSerializeTD) -> BaseUnitStatus:
        """Deserialize a dictionary into a :class:`BaseUnitStatus` object"""
        return cls(
            base_unit=BaseUnitInfo.deserialize(data["base_unit"]),
            current_uptime=datetime.timedelta(seconds=data["current_uptime_seconds"]),
            total_uptime=datetime.timedelta(seconds=data["total_uptime_seconds"]),
            error_code=data["error_code"],
            error_message=data["error_message"],
            first_used=datetime.datetime.fromisoformat(data["first_used"]),
            in_use=data["in_use"],
            sharing=data["sharing"],
        )

    def as_timezone(self, tz: datetime.tzinfo) -> BaseUnitStatus:
        """Return a copy of this BaseUnitStatus with the first_used timestamp converted to the given timezone"""
        if self.first_used.tzinfo is None:
            raise ValueError("Cannot convert timezone of naive datetime")
        return BaseUnitStatus(
            base_unit=self.base_unit,
            current_uptime=self.current_uptime,
            total_uptime=self.total_uptime,
            error_code=self.error_code,
            error_message=self.error_message,
            first_used=self.first_used.astimezone(tz),
            in_use=self.in_use,
            sharing=self.sharing,
        )


type LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LogLevels: tuple[LogLevel, ...] = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

type SensorType = Literal["CPU", "WLAN0", "WLAN1"]
SensorTypes: tuple[SensorType, ...] = ("CPU", "WLAN0", "WLAN1")


type SSLOptions = SSLContext|Fingerprint|bool

class AioHttpRequestOptions(TypedDict):
    """Options for making an HTTP request with aiohttp."""
    auth: NotRequired[BasicAuth | None]
    cookies: NotRequired[LooseCookies | None]
    headers: NotRequired[LooseHeaders | None]
    proxy: NotRequired[StrOrURL | None]
    proxy_auth: NotRequired[BasicAuth | None]
    ssl: NotRequired[SSLOptions]
    proxy_headers: NotRequired[LooseHeaders | None]
    middlewares: NotRequired[Sequence[ClientMiddlewareType]]


class AioHttpSessionOptions(TypedDict):
    """Options for creating an aiohttp ClientSession."""
    auth: NotRequired[BasicAuth | None]
    connector: NotRequired[BaseConnector | None]
    cookies: NotRequired[LooseCookies | None]
    headers: NotRequired[LooseHeaders | None]
    middlewares: NotRequired[Sequence[ClientMiddlewareType]]
    proxy: NotRequired[StrOrURL | None]
    proxy_auth: NotRequired[BasicAuth | None]
