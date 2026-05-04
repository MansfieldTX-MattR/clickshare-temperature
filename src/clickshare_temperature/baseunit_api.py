from __future__ import annotations
import asyncio
from typing import Literal, Awaitable, Unpack, Callable, Any, AsyncGenerator, overload
from contextlib import asynccontextmanager

from aiohttp import ClientSession, BasicAuth, ClientResponse
from yarl import URL

from .types import (
    BaseUnitInfo, AuthInfo, AioHttpSessionOptions, AioHttpRequestOptions,
)

DEFAULT_REQUEST_OPTIONS: AioHttpRequestOptions = {
    "ssl": False,
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
) -> AsyncGenerator[ClientResponse, None]:
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
        data = await response.json()
        return data["hostname"]


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
        data = await response.json()
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
