from __future__ import annotations
from typing import NamedTuple, TypedDict, Unpack, Self
import datetime
from pathlib import Path
from dataclasses import dataclass, field
import re

from aiohttp import ClientSession

from .baseunit_api import download_logs, get_baseunit_info
from .log_archive import LogArchive, LogEntry, TmpDir
from .utils import get_baseunit_from_filename
from .types import (
    SensorType, SensorTypes, AuthInfo, AioHttpSessionOptions, AioHttpRequestOptions,
    BaseUnitInfo, BaseUnitInfoSerializeTD,
)

CPU_TEMP_PATTERN = re.compile(r"Sensor readout CPUTemperature = (\d+(?:\.\d+)?) C")
WLAN_TEMP_PATTERN = re.compile(r"Temperature of (wlan\d): (\d+(?:\.\d+)?)")
CPU_FAN_SPEED_PATTERN = re.compile(r"Sensor readout CPUFanSpeed = (\d+(?:\.\d+)?) RPM")


class _SensorReadingSerializeTD[_T: SensorType](TypedDict):
    timestamp: str
    sensor: _T
    value: float


class SensorReading[T: SensorType](NamedTuple):
    """A sensor reading from the BaseUnit."""
    timestamp: datetime.datetime
    """Timestamp of the reading."""
    sensor: T
    """Type of sensor that the reading is from."""
    value: float
    """Temperature value in degrees Celsius."""

    @property
    def unit(self) -> str:
        """Get the unit for this sensor reading (e.g. "°C", "RPM", etc.)
        """
        if self.sensor == "CPU_FAN":
            return "rpm"
        return "°C"

    def as_timezone(self, tzinfo: datetime.tzinfo) -> SensorReading[T]:
        """Return a copy of this SensorReading with the timestamp converted to the given timezone."""
        return SensorReading(
            timestamp=self.timestamp.astimezone(tzinfo),
            sensor=self.sensor,
            value=self.value,
        )

    def serialize(self) -> _SensorReadingSerializeTD[T]:
        """Serialize the SensorReading to a dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "sensor": self.sensor,
            "value": self.value,
        }

    @staticmethod
    def deserialize[_T: SensorType](data: _SensorReadingSerializeTD[_T]) -> SensorReading[_T]:
        """Deserialize a SensorReading from a dictionary."""
        timestamp = datetime.datetime.fromisoformat(data["timestamp"])
        sensor = data["sensor"]
        value = data["value"]
        return SensorReading(timestamp=timestamp, sensor=sensor, value=value)

    def serialize_str(self) -> str:
        """Serialize the SensorReading to a string."""
        return f"{self.timestamp.isoformat()} {self.sensor} {self.value:.2f}{self.unit}"

    @staticmethod
    def deserialize_str(s: str) -> SensorReading[SensorType]:
        """Deserialize a SensorReading from a string."""
        timestamp_str, sensor_str, value_str = s.split()
        timestamp = datetime.datetime.fromisoformat(timestamp_str)
        sensor = sensor_str
        assert sensor in SensorTypes, f"Invalid sensor type: {sensor_str}"
        assert sensor is not None
        value = float(value_str.rstrip("°C").rstrip("rpm"))
        return SensorReading(timestamp=timestamp, sensor=sensor, value=value)


class _TemperatureHistorySerializeTD(TypedDict):
    base_unit: BaseUnitInfoSerializeTD
    readings: list[_SensorReadingSerializeTD[SensorType]]


@dataclass
class TemperatureHistory:
    """Temperature history for a BaseUnit."""
    base_unit: BaseUnitInfo
    readings: list[SensorReading[SensorType]] = field(default_factory=list)
    readings_by_timestamp: dict[datetime.datetime, dict[SensorType, SensorReading[SensorType]]] = field(default_factory=dict)

    @classmethod
    def from_archive_file(cls, archive_file: Path) -> Self:
        """Create a TemperatureHistory from a log archive file."""
        base_unit = get_baseunit_from_filename(archive_file)
        archive = LogArchive()
        archive.parse_archive_file(archive_file)
        readings = []
        readings_by_timestamp: dict[datetime.datetime, dict[SensorType, SensorReading[SensorType]]] = {}
        for entry in archive.all_entries(unique=True):
            reading = cls._parse_archive_entry(entry)
            if reading is not None:
                readings.append(reading)
                if reading.timestamp not in readings_by_timestamp:
                    readings_by_timestamp[reading.timestamp] = {}
                readings_by_timestamp[reading.timestamp][reading.sensor] = reading
        return cls(base_unit=base_unit, readings=readings, readings_by_timestamp=readings_by_timestamp)

    @classmethod
    def from_archive_bytes(cls, base_unit: BaseUnitInfo, archive_bytes: bytes) -> Self:
        """Create a TemperatureHistory from a log archive file in bytes."""
        archive = LogArchive()
        archive.parse_archive_bytes(archive_bytes)
        readings = []
        readings_by_timestamp: dict[datetime.datetime, dict[SensorType, SensorReading[SensorType]]] = {}
        for entry in archive.all_entries(unique=True):
            reading = cls._parse_archive_entry(entry)
            if reading is not None:
                readings.append(reading)
                if reading.timestamp not in readings_by_timestamp:
                    readings_by_timestamp[reading.timestamp] = {}
                readings_by_timestamp[reading.timestamp][reading.sensor] = reading
        return cls(base_unit=base_unit, readings=readings, readings_by_timestamp=readings_by_timestamp)

    @classmethod
    async def from_baseunit(
        cls,
        baseunit_ip: str,
        auth_info: AuthInfo,
        session: ClientSession|None = None,
        session_options: AioHttpSessionOptions|None = None,
        **request_options: Unpack[AioHttpRequestOptions]
    ) -> Self:
        """Create a TemperatureHistory by downloading logs from the BaseUnit."""
        base_unit = await get_baseunit_info(
            baseunit_ip,
            auth_info=auth_info,
            session=session,
            session_options=session_options,
            **request_options,
        )
        with TmpDir() as tmpdir:
            archive_path = tmpdir / "logs.tar.gz"
            with archive_path.open("wb") as f:
                await download_logs(
                    baseunit_ip,
                    chunk_handler=f.write,
                    auth_info=auth_info,
                    session=session,
                    session_options=session_options,
                    **request_options
                )
            return cls.from_archive_bytes(base_unit, archive_path.read_bytes())

    @classmethod
    def _parse_archive_entry(cls, entry: LogEntry) -> SensorReading[SensorType]|None:
        if entry.process == "CentralStore":
            cpu_temp_match = CPU_TEMP_PATTERN.search(entry.message)
            if cpu_temp_match:
                value = float(cpu_temp_match.group(1))
                return SensorReading(timestamp=entry.timestamp, sensor="CPU", value=value)
            cpu_fan_match = CPU_FAN_SPEED_PATTERN.search(entry.message)
            if cpu_fan_match:
                value = float(cpu_fan_match.group(1))
                return SensorReading(timestamp=entry.timestamp, sensor="CPU_FAN", value=value)
        elif entry.process == "NetworkManager":
            wlan_temp_match = WLAN_TEMP_PATTERN.search(entry.message)
            if wlan_temp_match:
                sensor = wlan_temp_match.group(1).upper()
                if sensor not in SensorTypes:
                    print(f"Warning: could not determine sensor for NetworkManager entry: {entry.message}")
                    return None
                value = float(wlan_temp_match.group(2))
                return SensorReading(timestamp=entry.timestamp, sensor=sensor, value=value)
        return None

    def combine_with(self, other: Self) -> Self:
        """Combine this TemperatureHistory with another one, merging their readings."""
        # combined_readings = self.readings + other.readings
        # combined_readings_by_timestamp: dict[datetime.datetime, dict[SensorType, SensorReading[SensorType]]] = {}
        for reading in other.readings:
            if reading in self:
                continue
            if reading.timestamp not in self.readings_by_timestamp:
                self.readings_by_timestamp[reading.timestamp] = {}
            # if reading.sensor in self.readings_by_timestamp[reading.timestamp]:
            #     existing_reading = self.readings_by_timestamp[reading.timestamp][reading.sensor]
            #     if existing_reading.value != reading.value:
            #         print(f"Warning: conflicting readings for {reading.sensor} at {reading.timestamp}: {existing_reading.value}°C vs {reading.value}°C. Using the latter.")
            #     else:
            #         # avoid adding duplicate readings with the same timestamp and sensor
            #         continue
            self.readings_by_timestamp[reading.timestamp][reading.sensor] = reading
        self.readings.sort(key=lambda r: r.timestamp)
        self.readings_by_timestamp = dict(sorted(self.readings_by_timestamp.items()))
        return self
        # return TemperatureHistory(readings=self.readings, readings_by_timestamp=self.readings_by_timestamp)


    def get_current(self) -> dict[SensorType, SensorReading[SensorType]]:
        """Get the most recent reading for each sensor."""
        current_readings: dict[SensorType, SensorReading[SensorType]] = {}
        for reading in self.readings:
            current_readings[reading.sensor] = reading
        return current_readings

    def serialize_current_str(self) -> str:
        """Serialize the most recent readings for each sensor to a string."""
        current_readings = self.get_current()
        return "\n".join(
            f"{reading.sensor}: {reading.value}{reading.unit}"
            for reading in current_readings.values()
        )

    def __contains__(self, reading: SensorReading[SensorType]) -> bool:
        """Check if a SensorReading is in the TemperatureHistory."""
        if reading.timestamp not in self.readings_by_timestamp:
            return False
        if reading.sensor not in self.readings_by_timestamp[reading.timestamp]:
            return False
        existing_reading = self.readings_by_timestamp[reading.timestamp][reading.sensor]
        if existing_reading.value != reading.value:
            print(f"Warning: conflicting readings for {reading.sensor} at {reading.timestamp}: {existing_reading.value} vs {reading.value}. Considering them as the same reading for containment check.")
        return True


    def serialize(self) -> _TemperatureHistorySerializeTD:
        """Serialize the TemperatureHistory to a dictionary."""
        return {
            "base_unit": self.base_unit.serialize(),
            "readings": [reading.serialize() for reading in self.readings],
        }

    @classmethod
    def deserialize(cls, data: _TemperatureHistorySerializeTD) -> Self:
        """Deserialize a TemperatureHistory from a dictionary."""
        base_unit = BaseUnitInfo.deserialize(data["base_unit"])
        readings = [SensorReading.deserialize(reading_data) for reading_data in data["readings"]]
        readings_by_timestamp: dict[datetime.datetime, dict[SensorType, SensorReading[SensorType]]] = {}
        for reading in readings:
            if reading.timestamp not in readings_by_timestamp:
                readings_by_timestamp[reading.timestamp] = {}
            readings_by_timestamp[reading.timestamp][reading.sensor] = reading
        return cls(base_unit=base_unit, readings=readings, readings_by_timestamp=readings_by_timestamp)

    def serialize_str(self) -> str:
        """Serialize the TemperatureHistory to a string."""
        return "\n".join(reading.serialize_str() for reading in self.readings)

    @classmethod
    def deserialize_str(cls, base_unit: BaseUnitInfo, s: str) -> Self:
        """Deserialize a TemperatureHistory from a string."""
        readings = [SensorReading.deserialize_str(line) for line in s.splitlines()]
        readings_by_timestamp: dict[datetime.datetime, dict[SensorType, SensorReading[SensorType]]] = {}
        for reading in readings:
            if reading.timestamp not in readings_by_timestamp:
                readings_by_timestamp[reading.timestamp] = {}
            readings_by_timestamp[reading.timestamp][reading.sensor] = reading
        return cls(base_unit=base_unit, readings=readings, readings_by_timestamp=readings_by_timestamp)
