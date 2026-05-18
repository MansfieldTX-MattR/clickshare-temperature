from __future__ import annotations
from typing import NamedTuple, TypedDict, Iterable, Self, Iterator
import datetime
import os
from pathlib import Path
import json
import enum
from contextlib import contextmanager

from dotenv import load_dotenv
from influxdb_client_3 import (
    InfluxDBClient3,
    Point,
    WritePrecision as _WritePrecision,
)
import click

from .temperature_history import SensorReading, TemperatureHistory
from .types import (
    BaseUnitInfo, BaseUnitStatus, BaseUnitUsageStatus, SensorType,
    PowerModeStatus,
)
from .utils import click_secho, get_baseunit_from_filename, get_app_dir


load_dotenv()


INFLUX_URL = os.getenv("INFLUX_URL", "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "my-influxdb-token")
INFLUX_ORG = os.getenv("INFLUX_ORG", "my-org")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "clickshare_temperature")


class WritePrecision(enum.Enum):
    """Enum mirroring the options for InfluxDB's `WritePrecision`

    As of the time of writing, InfluxDB's `WritePrecision` is not a true enum,
    it only defines class attributes for the different options.

    It is being defined as an enum here to allow for type safety and easier
    conversion to the string values expected by the InfluxDB client.
    """
    S = "s"
    MS = "ms"
    US = "us"
    NS = "ns"

    def to_influx_write_precision(self) -> str:
        """Convert this enum value to the string value expected by the InfluxDB client
        """
        result = getattr(_WritePrecision, self.name)
        assert isinstance(result, str)
        return result


type FieldType = str|int|float|bool
"""Type for InfluxDB field values, which can be strings, numbers, or booleans"""



def create_point(
    measurement_name: str,
    tags: dict[str, str],
    fields: dict[str, FieldType],
    timestamp: datetime.datetime,
    write_precision: WritePrecision
) -> Point:
    """Create an InfluxDB `Point` object with the given measurement name, tags, fields, and timestamp
    """
    assert timestamp.tzinfo is not None, "Timestamp must be timezone-aware"
    p = Point(measurement_name)                 # type: ignore[no-untyped-call]
    for tag_key, tag_value in tags.items():
        p.tag(tag_key, tag_value)               # type: ignore[no-untyped-call]
    for field_key, field_value in fields.items():
        p.field(field_key, field_value)         # type: ignore[no-untyped-call]
    p.time(timestamp, write_precision.to_influx_write_precision()) # type: ignore[no-untyped-call]
    return p


@contextmanager
def influxdb_client(host: str, token: str, org: str) -> Iterator[InfluxDBClient3]:
    """Context manager for creating and closing an InfluxDB client connection"""
    client = InfluxDBClient3(host=host, token=token, org=org) # type: ignore[no-untyped-call]
    try:
        yield client
    finally:
        client.close() # type: ignore[no-untyped-call]


class LastReadingInfoTD(TypedDict):
    """TypedDict for serializing :class:`LastReadingInfo` to JSON"""
    host_name: str
    timestamp: str
    sensor: SensorType


class LastReadingInfo(NamedTuple):
    """Information about the last reading uploaded for a specific sensor on a
    specific :class:`.BaseUnit`
    """
    host_name: str
    """Hostname of the BaseUnit this reading is for"""
    timestamp: datetime.datetime
    """Timestamp of the reading"""
    sensor: SensorType
    """Sensor type of the reading"""

    def serialize(self) -> LastReadingInfoTD:
        """Serialize this instance to a dictionary for JSON serialization
        """
        return {
            "host_name": self.host_name,
            "timestamp": self.timestamp.isoformat(),
            "sensor": self.sensor,
        }

    @classmethod
    def deserialize(cls, data: LastReadingInfoTD) -> Self:
        """Deserialize a dictionary into an instance
        """
        return cls(
            host_name=data["host_name"],
            timestamp=datetime.datetime.fromisoformat(data["timestamp"]),
            sensor=data["sensor"],
        )


class LastReadingsInfoTD(TypedDict):
    """TypedDict for serializing :class:`LastReadingsInfo` to JSON
    """
    readings: dict[str, dict[SensorType, LastReadingInfoTD]]

class LastReadingsInfo(NamedTuple):
    """Information about the last readings uploaded for all sensors on all BaseUnits
    """
    readings: dict[str, dict[SensorType, LastReadingInfo]]
    """Mapping of hostnames to sensor types to :class:`LastReadingInfo` instances
    """

    def get_last_timestamp_for_sensor(self, host_name: str, sensor: SensorType) -> datetime.datetime | None:
        """Get the timestamp of the last :class:`LastReadingInfo` for a specific
        sensor on a specific BaseUnit
        """
        if host_name not in self.readings:
            return None
        if sensor not in self.readings[host_name]:
            return None
        return self.readings[host_name][sensor].timestamp

    def can_upload_reading(self, host_name: str, reading: SensorReading[SensorType]) -> bool:
        """Determine if a reading can be uploaded based on the timestamp of the last
        uploaded reading for the same sensor on the same BaseUnit

        """
        last_timestamp = self.get_last_timestamp_for_sensor(host_name, reading.sensor)
        if last_timestamp is None:
            return True
        return reading.timestamp > last_timestamp

    def update_with_reading(self, host_name: str, reading: SensorReading[SensorType]) -> Self:
        """Update the last readings info with a new reading, returning a new instance with the updated info
        """
        updated_readings = {host: sensors.copy() for host, sensors in self.readings.items()}
        if host_name not in updated_readings:
            updated_readings[host_name] = {}
        updated_readings[host_name][reading.sensor] = LastReadingInfo(
            host_name=host_name,
            sensor=reading.sensor,
            timestamp=reading.timestamp,
        )
        return self.__class__(readings=updated_readings)

    @classmethod
    def get_storage_file(cls) -> Path:
        """Get the file path for storing the last readings info

        This will be located in the application data directory returned by
        :func:`get_app_dir` and will be named "last_uploaded_readings.json".
        """
        app_dir = get_app_dir()
        app_dir.mkdir(parents=True, exist_ok=True)
        return app_dir / "last_uploaded_readings.json"

    def save(self) -> None:
        """Save the last readings info to a file for later retrieval"""
        output_file = self.get_storage_file()
        output_file.write_text(json.dumps(self.serialize(), indent=2))

    @classmethod
    def load(cls) -> Self:
        """Load the last readings info from a file, or return an empty instance
        if the file does not exist
        """
        input_file = cls.get_storage_file()
        if not input_file.exists():
            return cls(readings={})
        data = json.loads(input_file.read_text())
        return cls.deserialize(data)


    def serialize(self) -> LastReadingsInfoTD:
        """Serialize this instance to a dictionary for JSON serialization
        """
        return {
            "readings": {
                host_name: {
                    sensor: info.serialize() for sensor, info in sensors.items()
                } for host_name, sensors in self.readings.items()
            }
        }

    @classmethod
    def deserialize(cls, data: LastReadingsInfoTD) -> Self:
        """Deserialize a dictionary into an instance
        """
        return cls(
            readings={
                host_name: {
                    sensor: LastReadingInfo.deserialize(info) for sensor, info in sensors.items()
                } for host_name, sensors in data["readings"].items()
            }
        )


def reading_to_point(base_unit: BaseUnitInfo, reading: SensorReading[SensorType]) -> Point:
    """Convert a :class:`.SensorReading` to an InfluxDB `Point` for uploading to InfluxDB
    """
    assert reading.timestamp.tzinfo is not None, "Reading timestamp must be timezone-aware"
    return create_point(
        measurement_name="temperature_reading",
        tags={
            "device_id": base_unit.hostname,
            "room_name": base_unit.room_name,
            "sensor": reading.sensor,
        },
        fields={
            "deg_c": reading.value,
        },
        timestamp=reading.timestamp,
        write_precision=WritePrecision.NS,
    )


def backfill_readings(
    base_unit: BaseUnitInfo,
    temperature_history: TemperatureHistory,
    ignore_last_readings_info: bool = False
) -> int:
    """Backfill sensor readings for a BaseUnit to InfluxDB, returning the number of points uploaded
    """
    if ignore_last_readings_info:
        readings_to_upload = list(temperature_history.readings)
    else:
        last_readings_info = LastReadingsInfo.load()
        readings_to_upload = []
        for r in temperature_history.readings:
            if last_readings_info.can_upload_reading(base_unit.hostname, r):
                readings_to_upload.append(r)
                last_readings_info = last_readings_info.update_with_reading(base_unit.hostname, r)
    if not len(readings_to_upload):
        return 0
    with influxdb_client(host=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
        points = [reading_to_point(base_unit, r) for r in readings_to_upload]
        client.write(database=INFLUX_BUCKET, record=points) # type: ignore[no-untyped-call]
        if not ignore_last_readings_info:
            last_readings_info.save()

        return len(points)


def baseunit_status_to_point(
    status: BaseUnitStatus|BaseUnitUsageStatus,
    timestamp: datetime.datetime
) -> Point:
    """Convert a :class:`.BaseUnitStatus` or :class:`.BaseUnitUsageStatus`
    object to an InfluxDB `Point` object for uploading to InfluxDB
    """
    assert timestamp.tzinfo is not None, "Timestamp must be timezone-aware"
    m_name = "baseunit_status" if isinstance(status, BaseUnitStatus) else "baseunit_usage_status"
    fields: dict[str, FieldType] = {
        "in_use": status.in_use,
        "sharing": status.sharing,
    }
    if isinstance(status, BaseUnitStatus):
        fields.update({
            "current_uptime_seconds": int(status.current_uptime.total_seconds()),
            "total_uptime_seconds": int(status.total_uptime.total_seconds()),
            "error_code": status.error_code,
            "error_message": status.error_message or "",
            "first_used_timestamp": int(status.first_used.timestamp()),
        })
    p = create_point(
        measurement_name=m_name,
        tags={
            "device_id": status.base_unit.hostname,
            "room_name": status.base_unit.room_name,
        },
        fields=fields,
        timestamp=timestamp,
        write_precision=WritePrecision.NS,
    )
    return p


def power_management_status_to_point(
    base_unit: BaseUnitInfo,
    mode: PowerModeStatus,
    timestamp: datetime.datetime
) -> Point:
    """Convert a :class:`.PowerManagementStatus` object to an InfluxDB `Point` object for
    uploading to InfluxDB
    """
    assert timestamp.tzinfo is not None, "Timestamp must be timezone-aware"
    return create_point(
        measurement_name="power_management_status",
        tags={
            "device_id": base_unit.hostname,
            "room_name": base_unit.room_name,
        },
        fields={
            "power_mode": mode,
        },
        timestamp=timestamp,
        write_precision=WritePrecision.NS,
    )


def upload_baseunit_status(
    statuses: Iterable[tuple[BaseUnitStatus|BaseUnitUsageStatus, datetime.datetime]]
) -> None:
    """Upload one or more :class:`.BaseUnitStatus` or :class:`.BaseUnitUsageStatus`
    objects to InfluxDB
    """
    with influxdb_client(host=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
        points = [
            baseunit_status_to_point(status, timestamp)
            for status, timestamp in statuses
        ]
        client.write(database=INFLUX_BUCKET, record=points) # type: ignore[no-untyped-call]


def upload_power_management_statuses(
    statuses: Iterable[tuple[BaseUnitInfo, PowerModeStatus, datetime.datetime]]
) -> None:
    """Upload one or more :class:`.PowerManagementStatus` objects to InfluxDB
    """
    with influxdb_client(host=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
        points = [
            power_management_status_to_point(base_unit, mode, timestamp)
            for base_unit, mode, timestamp in statuses
        ]
        client.write(database=INFLUX_BUCKET, record=points) # type: ignore[no-untyped-call]


def load_temperature_history_from_file(filepath: Path) -> TemperatureHistory:
    """Load a :class:`.TemperatureHistory` object from a file

    The :class:`.BaseUnitInfo` will be extracted from the filename as
    described in :func:`get_baseunit_from_filename`.
    """
    base_unit = get_baseunit_from_filename(filepath)
    data = filepath.read_text()
    temperature_history = TemperatureHistory.deserialize_str(base_unit, data)
    return temperature_history


def backfill_from_file(filepath: Path) -> None:
    """Backfill sensor readings from a file to InfluxDB

    The file given will be used to load a :class:`.TemperatureHistory` object
    using :func:`load_temperature_history_from_file`,
    and then the readings will be backfilled to InfluxDB using :func:`backfill_readings`.
    """
    temperature_history = load_temperature_history_from_file(filepath)
    base_unit = temperature_history.base_unit
    click_secho(f"Loaded temperature history for BaseUnit {base_unit} with {len(temperature_history.readings)} readings.")
    num_points = backfill_readings(base_unit, temperature_history)
    if num_points > 0:
        click_secho(f"Backfilled {num_points} points for BaseUnit {base_unit.hostname} to InfluxDB.", fg="bright_green")
    else:
        click_secho(f"No new readings to backfill for BaseUnit {base_unit.hostname}.", fg="blue")


def backfill_from_directory(directory: Path) -> None:
    """Backfill sensor readings from all files in a directory to InfluxDB using
    :func:`backfill_from_file`
    """
    for filepath in directory.glob("*.txt"):
        backfill_from_file(filepath)


@click.group(name="grafana")
def cli() -> None:
    """CLI for managing ClickShare temperature data and Grafana backfilling."""
    pass

@cli.command(name="backfill")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
def backfill_from_path(path: Path) -> None:
    """Backfill historical temperature data from a file or all files in a directory."""
    if path.is_file():
        backfill_from_file(path)
    elif path.is_dir():
        backfill_from_directory(path)
    else:
        click_secho(f"Path {path} is neither a file nor a directory, skipping.", fg="red")



if __name__ == "__main__":
    cli()
