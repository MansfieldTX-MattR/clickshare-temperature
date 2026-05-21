from __future__ import annotations
from dataclasses import dataclass
import click


from click_extra import (
    TimerOption,
    ColorOption,
    ThemeOption,
    ShowParamsOption,
    ExtraVersionOption,
)

from clickshare_temperature.types import AuthInfo


def get_extra_params() -> list[click.Option]:
    """Get the extra parameters for the ClickShare CLI commands."""
    return [
        TimerOption(),
        ColorOption(),
        ThemeOption(),
        ShowParamsOption(),
        ExtraVersionOption(),
    ]

@dataclass
class CLIRootContext:
    """Root context object for the CLI
    """
    auth_info: AuthInfo
    """Authentication information for the ClickShare device"""
