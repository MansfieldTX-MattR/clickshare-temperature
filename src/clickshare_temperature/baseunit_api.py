from __future__ import annotations

import asyncio
import datetime
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import (
    Any,
    Literal,
    TypedDict,
    Unpack,
    overload,
)

from aiohttp import BasicAuth, ClientResponse, ClientSession, ClientTimeout
from yarl import URL

from . import timezone
from .types import (
    AioHttpRequestOptions,
    AioHttpSessionOptions,
    AuthInfo,
    BaseUnitIdentity,
    BaseUnitInfo,
    BaseUnitStatus,
    BaseUnitStatusErrorCode,
    PowerManagementInfo,
    PowerMode,
    PowerModeStatus,
    PowerStandbyTimeout,
)

DEFAULT_REQUEST_OPTIONS: AioHttpRequestOptions = {
    "ssl": False,
    "timeout": ClientTimeout(total=10),
}

DEFAULT_SESSION_OPTIONS: AioHttpSessionOptions = {}


type CoroFunc[T] = Callable[..., Awaitable[T]]
type ChunkHandler = Callable[[bytes], Any]



def create_session(**options: Unpack[AioHttpSessionOptions]) -> ClientSession:
    """Create an aiohttp ClientSession with the given options."""
    return ClientSession(**options)


def get_baseunit_api_url(baseunit_ip: str) -> URL:
    """Get the URL for the BaseUnit API."""
    return URL(f"https://{baseunit_ip}:4003/v2")


def get_log_download_url(baseunit_ip: str) -> URL:
    """Get the URL for downloading logs from the BaseUnit.

    A GET request to this URL will trigger the download of the logs as a .tar.gz file.
    """
    return get_baseunit_api_url(baseunit_ip) / "configuration/troubleshooting/logs"

@asynccontextmanager
async def api_request(
    baseunit_ip: str,
    api_path: str,
    /,
    auth_info: AuthInfo|None = None,
    session: ClientSession|None = None,
    session_options: AioHttpSessionOptions|None = None,
    **request_options: Unpack[AioHttpRequestOptions],
) -> AsyncGenerator[ClientResponse]:
    """Make an API request to the BaseUnit."""
    url = get_baseunit_api_url(baseunit_ip) / api_path
    if auth_info is not None:
        auth = BasicAuth(auth_info.username, auth_info.password)
        request_options["auth"] = auth
    owns_session = False
    if session is None:
        if session_options is None:
            session_options = {}
        session = create_session(**session_options)
        owns_session = True
    try:
        response = await session.get(url, **request_options)
        response.raise_for_status()
        yield response
    finally:
        if owns_session:
            await session.close()



class _SystemNetworkResponse(TypedDict):
    hostname: str


async def get_baseunit_hostname(
    baseunit_ip: str,
    /,
    auth_info: AuthInfo|None = None,
    session: ClientSession|None = None,
    session_options: AioHttpSessionOptions|None = None,
    **request_options: Unpack[AioHttpRequestOptions],
) -> str:
    """Get the hostname of the BaseUnit."""
    async with api_request(
        baseunit_ip,
        "configuration/system/network",
        auth_info=auth_info,
        session=session,
        session_options=session_options,
        **request_options,
    ) as response:
        data: _SystemNetworkResponse = await response.json()
        return data["hostname"]



class _PersonalizationResponse(TypedDict):
    meetingRoomName: str


async def get_baseunit_roomname(
    baseunit_ip: str,
    /,
    auth_info: AuthInfo|None = None,
    session: ClientSession|None = None,
    session_options: AioHttpSessionOptions|None = None,
    **request_options: Unpack[AioHttpRequestOptions],
) -> str:
    """Get the room name of the BaseUnit."""
    async with api_request(
        baseunit_ip,
        "configuration/personalization",
        auth_info=auth_info,
        session=session,
        session_options=session_options,
        **request_options,
    ) as response:
        data: _PersonalizationResponse = await response.json()
        return data["meetingRoomName"]


async def get_baseunit_info(
    baseunit_ip: str,
    /,
    auth_info: AuthInfo|None = None,
    session: ClientSession|None = None,
    session_options: AioHttpSessionOptions|None = None,
    **request_options: Unpack[AioHttpRequestOptions],
) -> BaseUnitInfo:
    """Get the :class:`.BaseUnitInfo` for the BaseUnit at the given IP address
    """
    async def get_from_api(
        key: Literal["hostname", "room_name"],
        function: CoroFunc[str]
    ) -> tuple[Literal["hostname", "room_name"], str]:
        value = await function(
            baseunit_ip,
            auth_info=auth_info,
            session=session,
            session_options=session_options,
            **request_options,
        )
        return key, value
    results = await asyncio.gather(
        get_from_api("hostname", get_baseunit_hostname),
        get_from_api("room_name", get_baseunit_roomname),
    )
    result_dict = {key: value for key, value in results}
    return BaseUnitInfo(
        ip_address=baseunit_ip,
        hostname=result_dict["hostname"],
        room_name=result_dict["room_name"],
    )

class BaseUnitIdentityResponse(TypedDict):
    articleNumber: str
    hardwareVersion: str
    modelName: str
    productName: str
    serialNumber: str


async def get_baseunit_identity(
    baseunit_ip: str,
    /,
    auth_info: AuthInfo|None = None,
    session: ClientSession|None = None,
    session_options: AioHttpSessionOptions|None = None,
    **request_options: Unpack[AioHttpRequestOptions],
) -> BaseUnitIdentity:
    """Get the :class:`.BaseUnitIdentity` for the BaseUnit at the given IP address
    """
    async with api_request(
        baseunit_ip,
        "configuration/system/device-identity",
        auth_info=auth_info,
        session=session,
        session_options=session_options,
        **request_options,
    ) as response:
        data: BaseUnitIdentityResponse = await response.json()
        return BaseUnitIdentity(
            article_number=data["articleNumber"],
            hardware_version=data["hardwareVersion"],
            model_name=data["modelName"],
            product_name=data["productName"],
            serial_number=data["serialNumber"],
        )



class PowerManagementResponse(TypedDict):
    """Response for the power management API endpoint
    """
    powerMode: PowerMode
    """Current power mode of the BaseUnit (e.g. "EcoStandby")"""
    standbyTimeout: PowerStandbyTimeout
    """Current standby timeout of the BaseUnit"""
    status: PowerModeStatus
    """Current power status of the BaseUnit (e.g. "On")"""
    supportedPowerModes: list[PowerMode]
    """List of supported power modes"""
    supportedStandbyTimeouts: list[PowerStandbyTimeout]
    """List of supported standby timeouts"""
    supportedStatuses: list[PowerModeStatus]
    """List of supported power statuses"""


async def get_power_management_info(
    baseunit_ip: str,
    /,
    auth_info: AuthInfo|None = None,
    session: ClientSession|None = None,
    session_options: AioHttpSessionOptions|None = None,
    **request_options: Unpack[AioHttpRequestOptions],
) -> PowerManagementInfo:
    """Get the power management information for the BaseUnit at the given IP address
    """
    async with api_request(
        baseunit_ip,
        "configuration/system/power-management",
        auth_info=auth_info,
        session=session,
        session_options=session_options,
        **request_options,
    ) as response:
        data: PowerManagementResponse = await response.json()
        timeout = PowerManagementInfo.parse_standby_timeout(data["standbyTimeout"])
        return PowerManagementInfo(
            power_mode=data["powerMode"],
            standby_timeout_string=data["standbyTimeout"],
            standby_timeout_minutes=timeout,
            status=data["status"],
            supported_power_modes=data["supportedPowerModes"],
            supported_standby_timeouts=data["supportedStandbyTimeouts"],
            supported_statuses=data["supportedStatuses"],
        )


class BaseUnitStatusResponse(TypedDict):
    currentUptime: int
    """Current uptime of the BaseUnit in seconds"""
    errorCode: BaseUnitStatusErrorCode
    """Error code indicating the status of the BaseUnit"""
    errorMessage: str
    """Error message if the error code is not "Ok" (otherwise an empty string)"""
    firstUsed: str
    """Timestamp of when the BaseUnit was first used in isoformat"""
    inUse: bool
    """Whether the BaseUnit is currently in use"""
    sharing: bool
    """Whether the BaseUnit is currently sharing"""
    totalUptime: int
    """Total uptime of the BaseUnit in seconds"""


async def get_baseunit_status(
    baseunit_ip: str,
    /,
    auth_info: AuthInfo|None = None,
    session: ClientSession|None = None,
    session_options: AioHttpSessionOptions|None = None,
    **request_options: Unpack[AioHttpRequestOptions],
) -> BaseUnitStatus:
    """Get the :class:`.BaseUnitStatus` for the BaseUnit at the given IP address
    """
    async with api_request(
        baseunit_ip,
        "configuration/system/status",
        auth_info=auth_info,
        session=session,
        session_options=session_options,
        **request_options,
    ) as response:
        data: BaseUnitStatusResponse = await response.json()
        first_used = datetime.datetime.fromisoformat(data["firstUsed"])
        if not timezone.is_aware(first_used):
            tz = timezone.get_local_timezone(raise_exc=True)
            first_used = timezone.make_aware(first_used, tz)
        return BaseUnitStatus(
            base_unit=await get_baseunit_info(
                baseunit_ip,
                auth_info=auth_info,
                session=session,
                session_options=session_options,
                **request_options,
            ),
            current_uptime=datetime.timedelta(seconds=data["currentUptime"]),
            total_uptime=datetime.timedelta(seconds=data["totalUptime"]),
            error_code=data["errorCode"],
            error_message=None if not len(data["errorMessage"].strip()) else data["errorMessage"],
            first_used=first_used,
            in_use=data["inUse"],
            sharing=data["sharing"],
        )


@overload
async def download_logs(
    baseunit_ip: str,
    /,
    chunk_handler: ChunkHandler,
    chunk_size: int = ...,
    auth_info: AuthInfo|None = ...,
    session: ClientSession|None = ...,
    session_options: AioHttpSessionOptions|None = ...,
    **request_options: Unpack[AioHttpRequestOptions],
) -> None: ...
@overload
async def download_logs(
    baseunit_ip: str,
    /,
    chunk_handler: None = None,
    chunk_size: int = ...,
    auth_info: AuthInfo|None = ...,
    session: ClientSession|None = ...,
    session_options: AioHttpSessionOptions|None = ...,
    **request_options: Unpack[AioHttpRequestOptions],
) -> bytes: ...
async def download_logs(
    baseunit_ip: str,
    /,
    chunk_handler: ChunkHandler|None = None,
    chunk_size: int = 1024,
    auth_info: AuthInfo|None = None,
    session: ClientSession|None = None,
    session_options: AioHttpSessionOptions|None = None,
    **request_options: Unpack[AioHttpRequestOptions],
) -> bytes|None:
    """Download logs from the BaseUnit.

    This function will make a GET request to the log download URL and return the content of the response as bytes.
    """
    async with api_request(
        baseunit_ip,
        "configuration/troubleshooting/logs",
        auth_info=auth_info,
        session=session,
        session_options=session_options,
        **request_options,
    ) as response:
        if chunk_handler is not None:
            async for chunk in response.content.iter_chunked(chunk_size):
                chunk_handler(chunk)
            return None
        else:
            return await response.read()
