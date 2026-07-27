from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Unpack

import click
from aiohttp import ClientTimeout
from aiohttp.helpers import _SENTINEL, sentinel
from yarl import URL

from .baseunit_api import DEFAULT_REQUEST_OPTIONS
from .types import AioHttpRequestOptions, BaseUnitInfo

if TYPE_CHECKING:
    from .cli import OutputFormat



type ClickColor = Literal[
    "black",
    "red",
    "green",
    "yellow",
    "blue",
    "magenta",
    "cyan",
    "white",
    "bright_black",
    "bright_red",
    "bright_green",
    "bright_yellow",
    "bright_blue",
    "bright_magenta",
    "bright_cyan",
    "bright_white",
    "reset",
]

def click_secho(
    msg: str,
    nl: bool = True,
    err: bool = False,
    color: bool|None = None,
    fg: ClickColor|None = None,
    **styles: Any,
) -> None:
    """Wrapper around click.secho with a typed color argument"""
    click.secho(msg, nl=nl, err=err, color=color, fg=fg, **styles)


def get_output_file_for_baseunit(base_dir: Path, room_name: str, hostname: str, output_format: OutputFormat) -> Path:
    """Find the output file for a BaseUnit based on the room name and hostname.

    The file will be located in the specified base directory,
    and will have a name in the format "{room_name}.{hostname}.{ext}",
    where {ext} is either "txt" or "json" depending on the output format.

    If a file already exists in the base directory that matches the hostname
    and extension, that file will be used instead of creating a new one.

    This allows for appending to existing files if the room name has changed
    since the last download.
    """
    out_ext = "txt" if output_format in ("str", "current") else "json"
    for p in base_dir.glob(f"*.{hostname}.{out_ext}"):
        return p
    return base_dir / f"{room_name}.{hostname}.{out_ext}"


def get_baseunit_from_filename(filename: Path) -> BaseUnitInfo:
    """Extract the :class:`.BaseUnitInfo` from a filename

    The filename is expected to be in the format "{room_name}.{hostname}.{ext}",
    where {ext} can be any extension.
    """
    stem = filename.stem
    parts = stem.split(".")
    if len(parts) < 2:
        raise ValueError(f"Filename {filename} does not contain enough parts to extract room name and hostname.")
    room_name = ".".join(parts[:-1])
    hostname = parts[-1]
    return BaseUnitInfo(
        ip_address="",
        hostname=hostname,
        room_name=room_name,
    )


def get_app_name() -> str:
    """Get the application name for storing data."""
    name = __package__
    if name is None:
        raise ValueError("Could not determine application name from package metadata.")
    if "." in name:
        name = name.split(".")[0]
    return name


def get_app_dir() -> Path:
    """Get the directory for storing application data."""
    return Path(click.get_app_dir(get_app_name()))


def is_valid_ip_or_hostname(value: str) -> bool:
    """Check if the given value is a valid IP address or hostname."""
    try:
        URL(f"http://{value}:1234/foo")
        return True
    except ValueError:
        return False


def build_aiohttp_request_options(
    timeout_seconds: float | None | _SENTINEL = sentinel,
    **kwargs: Unpack[AioHttpRequestOptions]
) -> AioHttpRequestOptions:
    """Build a dictionary of options for aiohttp requests

    This includes setting the timeout option based on the provided timeout_seconds
    (without requiring the caller to import aiohttp.ClientTimeout).
    """
    timeout: ClientTimeout|_SENTINEL|None
    if timeout_seconds is not sentinel:
        timeout = ClientTimeout(total=timeout_seconds)
    elif "timeout" in kwargs:
        timeout = kwargs["timeout"]
        del kwargs["timeout"]
    else:
        timeout = DEFAULT_REQUEST_OPTIONS.get("timeout", sentinel)
    options: AioHttpRequestOptions = {
        **DEFAULT_REQUEST_OPTIONS,
        "timeout": timeout,
        **kwargs,
    }
    return options
