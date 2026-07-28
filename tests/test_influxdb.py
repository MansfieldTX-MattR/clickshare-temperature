from __future__ import annotations

import datetime
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import NamedTuple

import pytest
from pytest_httpserver import HTTPServer

from clickshare_temperature.influxdb import (
    InfluxDBClient3Wrapper,
    Point,
    backfill_readings,
    upload_baseunit_online_statuses,
    upload_baseunit_status,
    upload_power_management_statuses,
)
from clickshare_temperature.temperature_history import (
    SensorReading,
    TemperatureHistory,
)
from clickshare_temperature.types import (
    BaseUnitInfo,
    BaseUnitStatus,
    BaseUnitUsageStatus,
    PowerManagementInfo,
    PowerModeStatus,
    SensorType,
)

type WithTimeStamp[T] = tuple[T, datetime.datetime]



class BaseUnitOnlineStatus(NamedTuple):
    """Information about the online status of a BaseUnit at a specific timestamp"""
    base_unit: BaseUnitInfo
    online: bool
    timestamp: datetime.datetime


@pytest.fixture
def power_management_statuses(
    sample_power_management_response_multiple_with_timestamp: list[WithTimeStamp[PowerManagementInfo]],
) -> tuple[BaseUnitInfo, list[tuple[PowerManagementInfo, datetime.datetime]]]:
    """Fixture providing sample power management status data for a base unit, with timestamps
    """
    base_unit = BaseUnitInfo(
        hostname="test-device",
        room_name="Test Room",
        ip_address="192.168.123.123",
    )
    statuses_with_timestamps = sample_power_management_response_multiple_with_timestamp
    return base_unit, statuses_with_timestamps


@pytest.fixture
def baseunit_online_statuses() -> list[BaseUnitOnlineStatus]:
    """Fixture providing sample online status data for multiple base units, with timestamps

    Each status is for one of two base units, alternating every status,
    with the online status alternating every third status, and timestamps
    starting from a fixed point and increasing by one minute for each status.
    """
    base_units = [
        BaseUnitInfo(
            hostname="device1",
            room_name="Room A",
            ip_address="192.168.1.101",
        ),
        BaseUnitInfo(
            hostname="device2",
            room_name="Room B",
            ip_address="192.168.1.102",
        )
    ]
    start_dt = datetime.datetime(2024, 1, 1, 12, 0, tzinfo=datetime.UTC)
    return [
        BaseUnitOnlineStatus(
            base_unit=base_units[i % 2],
            online=i % 3 == 0,
            timestamp=start_dt + datetime.timedelta(minutes=i),
        )
        for i in range(20)
    ]


@pytest.fixture(autouse=True)
def app_dir_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fixture to override the application directory to a temporary path for testing

    This ensures that tests do not read from or write to the actual application
    directory on the filesystem.
    """
    temp_app_dir = tmp_path / "app_dir"
    temp_app_dir.mkdir()
    monkeypatch.setattr("clickshare_temperature.influxdb.get_app_dir", lambda: temp_app_dir)


def test_app_dir_override() -> None:
    """Test that the application directory override fixture is working correctly
    """
    from clickshare_temperature.influxdb import LastReadingsInfo
    storage_file = LastReadingsInfo.get_storage_file().resolve()

    # The storage file should be located within the system's temporary directory,
    # not the default application directory
    system_temp_dir = Path(tempfile.gettempdir()).resolve()
    assert system_temp_dir in storage_file.parents




def test_client_wrapper_reentrancy(influxdb_client_env_mock: None) -> None:
    """Test that the InfluxDBClient3Wrapper nested context manager closes properly

    The wrapper should remain open for the duration of the outermost context,
    and should not close until the outermost context is exited, even if
    inner contexts are entered and exited.
    """
    influxdb_client = InfluxDBClient3Wrapper()
    with influxdb_client:
        assert influxdb_client.is_open
        with influxdb_client:
            assert influxdb_client.is_open
            with influxdb_client:
                assert influxdb_client.is_open
            assert influxdb_client.is_open
        assert influxdb_client.is_open
    assert not influxdb_client.is_open




def check_usage_status_points(
    points: Sequence[Point],
    statuses_with_timestamps: Sequence[WithTimeStamp[BaseUnitUsageStatus]],
    extra_tags: Sequence[dict[str, str]]|None = None,
) -> None:
    """Check that the given points match the expected usage statuses and timestamps,
    with optional extra tags
    """
    assert len(points) == len(statuses_with_timestamps)
    if extra_tags is not None:
        assert len(extra_tags) == len(statuses_with_timestamps)
    else:
        extra_tags = [{} for _ in statuses_with_timestamps]
    for point, (status, timestamp), tags in zip(points, statuses_with_timestamps, extra_tags):
        assert point.get_time() == timestamp
        expected_tags = {
            "device_id": status.base_unit.hostname,
            "room_name": status.base_unit.room_name,
        }
        expected_tags.update(tags)
        assert point.tags == expected_tags
        expected_fields = {
            "in_use": status.in_use,
            "sharing": status.sharing,
        }
        assert point.fields == expected_fields


def check_sensor_reading_points(
    points: Sequence[Point],
    readings: Sequence[SensorReading[SensorType]],
    base_unit: BaseUnitInfo,
    extra_tags: Sequence[dict[str, str]]|None = None,
) -> None:
    """Check that the given points match the expected sensor readings and timestamps,
    with optional extra tags
    """
    assert len(points) == len(readings)
    if extra_tags is not None:
        assert len(extra_tags) == len(readings)
    else:
        extra_tags = [{} for _ in readings]
    for point, reading, tags in zip(points, readings, extra_tags):
        assert point.get_time() == reading.timestamp
        expected_tags = {
            "device_id": base_unit.hostname,
            "room_name": base_unit.room_name,
            "sensor": reading.sensor,
        }
        expected_tags.update(tags)
        assert point.tags == expected_tags
        field_key = "rpm" if reading.sensor == "CPU_FAN" else "deg_c"
        expected_fields = {
            field_key: reading.value,
        }
        assert point.fields == expected_fields


def check_power_management_points(
    points: Sequence[Point],
    statuses_with_timestamps: Sequence[WithTimeStamp[PowerManagementInfo]],
    base_unit: BaseUnitInfo,
    extra_tags: Sequence[dict[str, str]]|None = None,
) -> None:
    """Check that the given points match the expected power management statuses and timestamps,
    with optional extra tags
    """
    assert len(points) == len(statuses_with_timestamps)
    if extra_tags is not None:
        assert len(extra_tags) == len(statuses_with_timestamps)
    else:
        extra_tags = [{} for _ in statuses_with_timestamps]
    for point, (power_info, timestamp), tags in zip(points, statuses_with_timestamps, extra_tags):
        assert point.get_time() == timestamp
        expected_tags = {
            "device_id": base_unit.hostname,
            "room_name": base_unit.room_name,
        }
        expected_tags.update(tags)
        assert point.tags == expected_tags
        expected_fields = {
            "power_mode": power_info.status,
        }
        assert point.fields == expected_fields


def check_online_status_points(
    points: Sequence[Point],
    statuses_with_timestamps: Sequence[BaseUnitOnlineStatus],
    extra_tags: Sequence[dict[str, str]]|None = None,
) -> None:
    """Check that the given points match the expected online statuses and timestamps,
    with optional extra tags
    """
    assert len(points) == len(statuses_with_timestamps)
    if extra_tags is not None:
        assert len(extra_tags) == len(statuses_with_timestamps)
    else:
        extra_tags = [{} for _ in statuses_with_timestamps]
    for point, status, tags in zip(points, statuses_with_timestamps, extra_tags):
        assert point.get_time() == status.timestamp
        expected_tags = {
            "device_id": status.base_unit.hostname,
            "room_name": status.base_unit.room_name,
        }
        expected_tags.update(tags)
        assert point.tags == expected_tags
        expected_fields = {
            "online": status.online,
        }
        assert point.fields == expected_fields



def test_usage_status_upload(
    influxdb_client: InfluxDBClient3Wrapper,
    sample_base_unit_usage_status_multiple_with_timestamp: list[WithTimeStamp[BaseUnitUsageStatus]],
) -> None:
    statuses = sample_base_unit_usage_status_multiple_with_timestamp
    with influxdb_client:
        points = upload_baseunit_status(
            statuses,
            client_wrapper=influxdb_client,
        )
    check_usage_status_points(points, statuses)


def test_usage_status_upload_with_extra_tags(
    influxdb_client: InfluxDBClient3Wrapper,
    sample_base_unit_usage_status_multiple_with_timestamp: list[WithTimeStamp[BaseUnitUsageStatus]],
) -> None:
    statuses = sample_base_unit_usage_status_multiple_with_timestamp
    def get_extra_tags(status: BaseUnitStatus|BaseUnitUsageStatus) -> dict[str, str]:
        return {
            "extra_tag_1": f"value1_{status.base_unit.hostname}",
            "extra_tag_2": f"value2_{status.base_unit.room_name}",
            "extra_tag_3": f"value3_{status.base_unit.hostname}_{status.in_use}",
        }
    extra_tags = [get_extra_tags(status) for status, _ in statuses]
    with influxdb_client:
        points = upload_baseunit_status(
            statuses,
            client_wrapper=influxdb_client,
            tags_callback=get_extra_tags,
        )
    check_usage_status_points(points, statuses, extra_tags=extra_tags)


def test_backfill_readings(
    influxdb_client: InfluxDBClient3Wrapper,
    sample_temperature_history: TemperatureHistory,
) -> None:
    base_unit = sample_temperature_history.base_unit
    readings = sample_temperature_history.readings
    with influxdb_client:
        num_points, points = backfill_readings(
            base_unit,
            temperature_history=sample_temperature_history,
            client_wrapper=influxdb_client,
            return_points=True,
        )
    assert num_points == len(readings)
    check_sensor_reading_points(points, readings, base_unit)


def test_backfill_readings_with_extra_tags(
    influxdb_client: InfluxDBClient3Wrapper,
    sample_temperature_history: TemperatureHistory,
) -> None:
    def get_extra_tags(base_unit: BaseUnitInfo, reading: SensorReading) -> dict[str, str]:
        return {
            "extra_tag_1": f"value1_{reading.sensor}",
            "extra_tag_2": f"value2_{reading.timestamp.isoformat()}",
            "extra_tag_3": f"value3_{reading.sensor}_{reading.value}",
        }
    base_unit = sample_temperature_history.base_unit
    readings = sample_temperature_history.readings

    extra_tags = [get_extra_tags(base_unit, reading) for reading in readings]
    with influxdb_client:
        num_points, points = backfill_readings(
            base_unit,
            temperature_history=sample_temperature_history,
            client_wrapper=influxdb_client,
            tags_callback=get_extra_tags,
            return_points=True,
        )
    assert num_points == len(readings)
    check_sensor_reading_points(points, readings, base_unit, extra_tags=extra_tags)



def test_upload_power_management_statuses(
    influxdb_client: InfluxDBClient3Wrapper,
    power_management_statuses: tuple[BaseUnitInfo, list[tuple[PowerManagementInfo, datetime.datetime]]],
) -> None:
    base_unit, statuses_with_timestamps = power_management_statuses
    with influxdb_client:
        statuses: list[tuple[BaseUnitInfo, PowerModeStatus, datetime.datetime]] = [
            (base_unit, item.status, timestamp)
            for item, timestamp in statuses_with_timestamps
        ]
        points = upload_power_management_statuses(
            statuses,
            client_wrapper=influxdb_client,
        )
    check_power_management_points(points, statuses_with_timestamps, base_unit)


def test_upload_power_management_statuses_with_extra_tags(
    influxdb_client: InfluxDBClient3Wrapper,
    power_management_statuses: tuple[BaseUnitInfo, list[tuple[PowerManagementInfo, datetime.datetime]]],
) -> None:
    def get_extra_tags(base_unit: BaseUnitInfo) -> dict[str, str]:
        return {
            "extra_tag_1": f"value1_{base_unit.hostname}",
            "extra_tag_2": f"value2_{base_unit.room_name}",
            "extra_tag_3": f"value3_{base_unit.hostname}",
        }
    base_unit, statuses_with_timestamps = power_management_statuses
    extra_tags = [get_extra_tags(base_unit) for _ in statuses_with_timestamps]
    with influxdb_client:
        statuses: list[tuple[BaseUnitInfo, PowerModeStatus, datetime.datetime]] = [
            (base_unit, item.status, timestamp)
            for item, timestamp in statuses_with_timestamps
        ]
        points = upload_power_management_statuses(
            statuses,
            client_wrapper=influxdb_client,
            tags_callback=get_extra_tags,
        )
    check_power_management_points(points, statuses_with_timestamps, base_unit, extra_tags=extra_tags)


def test_upload_online_statuses(
    influxdb_client: InfluxDBClient3Wrapper,
    baseunit_online_statuses: list[BaseUnitOnlineStatus],
) -> None:
    with influxdb_client:
        points = upload_baseunit_online_statuses(
            baseunit_online_statuses,
            client_wrapper=influxdb_client,
        )
    check_online_status_points(points, baseunit_online_statuses)


def test_upload_online_statuses_with_extra_tags(
    influxdb_client: InfluxDBClient3Wrapper,
    baseunit_online_statuses: list[BaseUnitOnlineStatus],
) -> None:
    def get_extra_tags(base_unit: BaseUnitInfo) -> dict[str, str]:
        return {
            "extra_tag_1": f"value1_{base_unit.hostname}",
            "extra_tag_2": f"value2_{base_unit.room_name}",
            "extra_tag_3": f"value3_{base_unit.hostname}",
        }
    extra_tags = [get_extra_tags(status.base_unit) for status in baseunit_online_statuses]
    with influxdb_client:
        points = upload_baseunit_online_statuses(
            baseunit_online_statuses,
            client_wrapper=influxdb_client,
            tags_callback=get_extra_tags,
        )
    check_online_status_points(points, baseunit_online_statuses, extra_tags=extra_tags)


def test_upload_multiple_status_types(
    influxdb_client: InfluxDBClient3Wrapper,
    influxdb_http_server: HTTPServer,
    sample_base_unit_usage_status_multiple_with_timestamp: list[WithTimeStamp[BaseUnitUsageStatus]],
    power_management_statuses: tuple[BaseUnitInfo, list[tuple[PowerManagementInfo, datetime.datetime]]],
    sample_temperature_history: TemperatureHistory,
    baseunit_online_statuses: list[BaseUnitOnlineStatus],
) -> None:
    """Test uploading multiple different types of status data in sequence

    All uploads should succeed and the client should remain open for the
    duration of the outer context.
    """
    usage_statuses = sample_base_unit_usage_status_multiple_with_timestamp
    base_unit, power_statuses = power_management_statuses
    temperature_history = sample_temperature_history

    with influxdb_client:
        usage_points = upload_baseunit_status(
            usage_statuses,
            client_wrapper=influxdb_client,
        )
        assert influxdb_client.is_open
        assert len(influxdb_http_server.log) == 1

        power_points = upload_power_management_statuses(
            [(base_unit, item.status, timestamp) for item, timestamp in power_statuses],
            client_wrapper=influxdb_client,
        )
        assert influxdb_client.is_open
        assert len(influxdb_http_server.log) == 2

        _, temp_points = backfill_readings(
            base_unit,
            temperature_history=temperature_history,
            client_wrapper=influxdb_client,
            return_points=True,
        )
        assert influxdb_client.is_open
        assert len(influxdb_http_server.log) == 3

        online_points = upload_baseunit_online_statuses(
            baseunit_online_statuses,
            client_wrapper=influxdb_client,
        )
        assert influxdb_client.is_open
        assert len(influxdb_http_server.log) == 4

    check_usage_status_points(usage_points, usage_statuses)
    check_power_management_points(power_points, power_statuses, base_unit)
    check_sensor_reading_points(temp_points, temperature_history.readings, base_unit)
    check_online_status_points(online_points, baseunit_online_statuses)
