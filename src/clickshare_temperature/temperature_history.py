from __future__ import annotations
from typing import NamedTuple, Literal, TypedDict
import asyncio
import datetime
from pathlib import Path
from dataclasses import dataclass, field

from aiohttp import ClientSession, BasicAuth

from .baseunit_api import download_logs
from .log_archive import LogArchive, LogEntry
from .types import SensorType, SensorTypes, AuthInfo



class SensorReading[T: SensorType](NamedTuple):
    """A sensor reading from the BaseUnit."""
    timestamp: datetime.datetime
    """Timestamp of the reading."""
    sensor: T
    """Type of sensor that the reading is from."""
    value: float
    """Temperature value in degrees Celsius."""

    class SerializeTD[_T: SensorType](TypedDict):
        timestamp: str
        sensor: _T
        value: float

    def serialize(self) -> SerializeTD[T]:
        """Serialize the SensorReading to a dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "sensor": self.sensor,
            "value": self.value,
        }

    @staticmethod
    def deserialize[_T: SensorType](data: SensorReading.SerializeTD[_T]) -> SensorReading[_T]:
        """Deserialize a SensorReading from a dictionary."""
        timestamp = datetime.datetime.fromisoformat(data["timestamp"])
        sensor = data["sensor"]
        value = data["value"]
        return SensorReading(timestamp=timestamp, sensor=sensor, value=value)

    def serialize_str(self) -> str:
        """Serialize the SensorReading to a string."""
        return f"{self.timestamp.isoformat()} {self.sensor} {self.value:.2f}°C"

    @staticmethod
    def deserialize_str(s: str):
        """Deserialize a SensorReading from a string."""
        timestamp_str, sensor_str, value_str = s.split()
        timestamp = datetime.datetime.fromisoformat(timestamp_str)
        sensor = sensor_str
        assert sensor in SensorTypes, f"Invalid sensor type: {sensor_str}"
        assert sensor is not None
        value = float(value_str.rstrip("°C"))
        return SensorReading(timestamp=timestamp, sensor=sensor, value=value)


@dataclass
class TemperatureHistory:
    """Temperature history for a BaseUnit."""
    readings: list[SensorReading[SensorType]] = field(default_factory=list)
    readings_by_timestamp: dict[datetime.datetime, dict[SensorType, SensorReading[SensorType]]] = field(default_factory=dict)

    class SerializeTD(TypedDict):
        readings: list[SensorReading.SerializeTD[SensorType]]

    @classmethod
    def from_archive_file(cls, archive_file: Path) -> TemperatureHistory:
        """Create a TemperatureHistory from a log archive file."""
        archive = LogArchive()
        archive.parse_archive_file(archive_file)
        readings = []
        readings_by_timestamp: dict[datetime.datetime, dict[SensorType, SensorReading[SensorType]]] = {}
        for log_file in archive.log_files:
            for entry in log_file.entries:
                reading = cls._parse_archive_entry(entry)
                if reading is not None:
                    readings.append(reading)
                    if reading.timestamp not in readings_by_timestamp:
                        readings_by_timestamp[reading.timestamp] = {}
                    readings_by_timestamp[reading.timestamp][reading.sensor] = reading
        return cls(readings=readings, readings_by_timestamp=readings_by_timestamp)

    @classmethod
    def from_archive_bytes(cls, archive_bytes: bytes) -> TemperatureHistory:
        """Create a TemperatureHistory from a log archive file in bytes."""
        archive = LogArchive()
        archive.parse_archive_bytes(archive_bytes)
        readings = []
        readings_by_timestamp: dict[datetime.datetime, dict[SensorType, SensorReading[SensorType]]] = {}
        for log_file in archive.log_files:
            for entry in log_file.entries:
                reading = cls._parse_archive_entry(entry)
                if reading is not None:
                    readings.append(reading)
                    if reading.timestamp not in readings_by_timestamp:
                        readings_by_timestamp[reading.timestamp] = {}
                    readings_by_timestamp[reading.timestamp][reading.sensor] = reading
        return cls(readings=readings, readings_by_timestamp=readings_by_timestamp)

    @classmethod
    async def from_baseunit(cls, baseunit_ip: str, auth: AuthInfo) -> TemperatureHistory:
        """Create a TemperatureHistory by downloading logs from the BaseUnit."""
        archive_bytes = await download_logs(baseunit_ip, auth=auth)
        return cls.from_archive_bytes(archive_bytes)

    @classmethod
    def _parse_archive_entry(cls, entry: LogEntry) -> SensorReading|None:
        if entry.process == "CentralStore":
            s = "Sensor readout CPUTemperature = "
            if s in entry.message:
                value = float(entry.message.split(s)[1].rstrip("°C"))
                return SensorReading(timestamp=entry.timestamp, sensor="CPU", value=value)
        elif entry.process == "NetworkManager":
            s = "Temperature of wlan1: "
            if s in entry.message:
                value = float(entry.message.split(s)[1].rstrip("°C"))
                return SensorReading(timestamp=entry.timestamp, sensor="WLAN", value=value)
        return None

    def combine_with(self, other: TemperatureHistory) -> TemperatureHistory:
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
        return "\n".join(f"{reading.sensor}: {reading.value}°C" for reading in current_readings.values())

    def __contains__(self, reading: SensorReading) -> bool:
        """Check if a SensorReading is in the TemperatureHistory."""
        if reading.timestamp not in self.readings_by_timestamp:
            return False
        if reading.sensor not in self.readings_by_timestamp[reading.timestamp]:
            return False
        existing_reading = self.readings_by_timestamp[reading.timestamp][reading.sensor]
        if existing_reading.value != reading.value:
            print(f"Warning: conflicting readings for {reading.sensor} at {reading.timestamp}: {existing_reading.value}°C vs {reading.value}°C. Considering them as the same reading for containment check.")
        return True


    def serialize(self) -> SerializeTD:
        """Serialize the TemperatureHistory to a dictionary."""
        return {
            "readings": [reading.serialize() for reading in self.readings],
        }

    @classmethod
    def deserialize(cls, data: SerializeTD) -> TemperatureHistory:
        """Deserialize a TemperatureHistory from a dictionary."""
        readings = [SensorReading.deserialize(reading_data) for reading_data in data["readings"]]
        readings_by_timestamp: dict[datetime.datetime, dict[SensorType, SensorReading[SensorType]]] = {}
        for reading in readings:
            if reading.timestamp not in readings_by_timestamp:
                readings_by_timestamp[reading.timestamp] = {}
            readings_by_timestamp[reading.timestamp][reading.sensor] = reading
        return cls(readings=readings, readings_by_timestamp=readings_by_timestamp)

    def serialize_str(self) -> str:
        """Serialize the TemperatureHistory to a string."""
        return "\n".join(reading.serialize_str() for reading in self.readings)

    @classmethod
    def deserialize_str(cls, s: str) -> TemperatureHistory:
        """Deserialize a TemperatureHistory from a string."""
        readings = [SensorReading.deserialize_str(line) for line in s.splitlines()]
        readings_by_timestamp: dict[datetime.datetime, dict[SensorType, SensorReading[SensorType]]] = {}
        for reading in readings:
            if reading.timestamp not in readings_by_timestamp:
                readings_by_timestamp[reading.timestamp] = {}
            readings_by_timestamp[reading.timestamp][reading.sensor] = reading
        return cls(readings=readings, readings_by_timestamp=readings_by_timestamp)
