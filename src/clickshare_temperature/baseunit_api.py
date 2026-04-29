from __future__ import annotations
from typing import NamedTuple, overload

from aiohttp import ClientSession
import aiohttp
from yarl import URL

from .types import AuthInfo





def get_baseunit_api_url(baseunit_ip: str) -> URL:
    """Get the URL for the BaseUnit API."""
    return URL(f"https://{baseunit_ip}:4003/v2")


def get_log_download_url(baseunit_ip: str) -> URL:
    """Get the URL for downloading logs from the BaseUnit.

    A GET request to this URL will trigger the download of the logs as a .tar.gz file.
    """
    return get_baseunit_api_url(baseunit_ip) / "configuration/troubleshooting/logs"


@overload
async def download_logs(baseunit_ip: str, /, auth: AuthInfo, session: None = ...) -> bytes: ...
@overload
async def download_logs(baseunit_ip: str, /, auth: None = ..., session: ClientSession = ...) -> bytes: ...
async def download_logs(baseunit_ip: str, /, auth: AuthInfo|None = None, session: ClientSession|None = None) -> bytes:
    """Download logs from the BaseUnit.

    This function will make a GET request to the log download URL and return the content of the response as bytes.
    """
    url = get_log_download_url(baseunit_ip)
    if session is None:
        if auth is None:
            raise ValueError("Either auth or session must be provided.")
        async with ClientSession(auth=aiohttp.BasicAuth(auth.username, auth.password)) as session:
            async with session.get(url, ssl=False) as response:
                response.raise_for_status()
                return await response.read()
    else:
        async with session.get(url, ssl=False) as response:
            response.raise_for_status()
            return await response.read()
