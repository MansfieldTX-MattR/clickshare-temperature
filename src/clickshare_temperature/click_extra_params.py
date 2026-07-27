from __future__ import annotations

from dataclasses import dataclass

import click
from click_extra import (
    ColorOption,
    ShowParamsOption,
    ThemeOption,
    TimerOption,
    VersionOption,
)

from clickshare_temperature.types import (
    AioHttpRequestOptions,
    AioHttpSessionOptions,
    AuthInfo,
)


def get_extra_params() -> list[click.Option]:
    """Get the extra parameters for the ClickShare CLI commands."""
    return [
        TimerOption(),
        ColorOption(),
        ThemeOption(),
        ShowParamsOption(),
        VersionOption(),
    ]

@dataclass
class CLIRootContext:
    """Root context object for the CLI
    """
    auth_info: AuthInfo
    """Authentication information for the ClickShare device"""
    aiohttp_request_options: AioHttpRequestOptions
    """Options for aiohttp requests"""
    aiohttp_session_options: AioHttpSessionOptions
    """Options for aiohttp sessions"""
