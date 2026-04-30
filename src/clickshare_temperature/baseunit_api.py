from __future__ import annotations
from typing import Unpack, overload

from aiohttp import ClientSession, BasicAuth
from yarl import URL

from .types import (
    AuthInfo, AioHttpSessionOptions, AioHttpRequestOptions,
)


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


async def download_logs(
    baseunit_ip: str,
    /,
    auth_info: AuthInfo|None = None,
    session: ClientSession|None = None,
    session_options: AioHttpSessionOptions|None = None,
    **request_options: Unpack[AioHttpRequestOptions],
) -> bytes:
    """Download logs from the BaseUnit.

    This function will make a GET request to the log download URL and return the content of the response as bytes.
    """
    url = get_log_download_url(baseunit_ip)
    if auth_info is not None:
        auth = BasicAuth(auth_info.username, auth_info.password)
        request_options["auth"] = auth
    if session is None:
        if session_options is None:
            session_options = {}

        async with create_session(**session_options) as session:
            async with session.get(url, **request_options) as response:
                response.raise_for_status()
                return await response.read()
    else:
        async with session.get(url, **request_options) as response:
            response.raise_for_status()
            return await response.read()
