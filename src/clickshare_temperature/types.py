from __future__ import annotations
from typing import Literal, Sequence, NamedTuple, TypedDict, NotRequired, TYPE_CHECKING

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
