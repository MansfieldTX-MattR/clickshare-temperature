from __future__ import annotations
from typing import NamedTuple, Literal, get_args


class AuthInfo(NamedTuple):
    """Authentication information for the BaseUnit API."""
    username: str
    password: str


type LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LogLevels: tuple[LogLevel, ...] = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

type SensorType = Literal["CPU", "WLAN"]
SensorTypes: tuple[SensorType, ...] = ("CPU", "WLAN")
