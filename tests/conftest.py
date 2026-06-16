import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

import pytest

from clickshare_temperature.types import (
    BaseUnitInfo,
    BaseUnitIdentity,
    BaseUnitStatus,
    BaseUnitUsageStatus,
    PowerManagementInfo,
)
from clickshare_temperature.temperature_history import TemperatureHistory, SensorReading

from log_data_helpers import (
    LOG_ARCHIVE_FILE,
    LOG_ARCHIVE_EXPECTED_FILES,
    LOG_ENTRY_TEST_CASES,
    LOG_ENTRY_SENSOR_READINGS,
    LogEntryTestCase,
)


type WithTimeStamp[T] = tuple[T, datetime.datetime]




@pytest.fixture(params=LOG_ENTRY_TEST_CASES)
def log_entry_test_case(request: pytest.FixtureRequest) -> LogEntryTestCase:
    """Fixture that provides each LogEntryTestCase as a separate test parameter
    """
    return request.param


@pytest.fixture
def log_entry_test_cases() -> list[LogEntryTestCase]:
    """Fixture that provides all LogEntryTestCases as a list
    """
    return LOG_ENTRY_TEST_CASES


@pytest.fixture
def log_entry_sensor_readings() -> list[SensorReading]:
    """Fixture that provides all SensorReadings as a list
    """
    return LOG_ENTRY_SENSOR_READINGS


@pytest.fixture
def log_archive_expected_files() -> list[Path]:
    """Fixture that provides the expected files in the log archive as a list
    """
    return LOG_ARCHIVE_EXPECTED_FILES


@pytest.fixture
def log_archive_file() -> Path:
    """Fixture that provides the path to the log archive file used for testing
    """
    return LOG_ARCHIVE_FILE


@pytest.fixture(
    params=[
        # ZoneInfo("UTC"),
        datetime.timezone.utc,
        ZoneInfo("US/Eastern"),
        ZoneInfo("US/Central"),
        ZoneInfo("US/Mountain"),
        ZoneInfo("US/Pacific"),
    ]
)
def tzinfo(request) -> datetime.tzinfo:
    """Fixture that provides different timezone info objects for testing."""
    return request.param

@pytest.fixture
def sample_base_unit_info() -> BaseUnitInfo:
    return BaseUnitInfo(
        hostname="test-baseunit",
        room_name="Test Room",
        ip_address="192.168.1.1",
    )

@pytest.fixture
def sample_base_unit_identity() -> BaseUnitIdentity:
    return BaseUnitIdentity(
        article_number="R9861511EU",
        hardware_version="1.0",
        model_name="ClickShare C-10",
        product_name="ClickShare C-10",
        serial_number="1234567890",
    )

@pytest.fixture
def sample_power_management_response() -> PowerManagementInfo:
    return PowerManagementInfo(
        power_mode="EcoStandby",
        standby_timeout_string="10",
        standby_timeout_minutes=10,
        status="Standby",
        supported_statuses=["On", "Standby"],
        supported_power_modes=["EcoStandby", "NetworkedStandby", "DeepStandby"],
        supported_standby_timeouts=["10", "30", "60", "Infinite"],
    )


@pytest.fixture
def sample_power_management_response_multiple(
    sample_power_management_response: PowerManagementInfo
) -> list[PowerManagementInfo]:
    """Fixture that provides multiple PowerManagementInfo objects with different statuses
    """
    return [
        sample_power_management_response,
        PowerManagementInfo(
            power_mode="EcoStandby",
            standby_timeout_string="10",
            standby_timeout_minutes=10,
            status="On",
            supported_statuses=["On", "Standby"],
            supported_power_modes=["EcoStandby", "NetworkedStandby", "DeepStandby"],
            supported_standby_timeouts=["10", "30", "60", "Infinite"],
        ),
    ]

@pytest.fixture
def sample_power_management_response_with_timestamp(
    sample_power_management_response: PowerManagementInfo,
    tzinfo: datetime.tzinfo
) -> WithTimeStamp[PowerManagementInfo]:
    timestamp = datetime.datetime(2024, 1, 1, 12, 0, tzinfo=tzinfo)
    return sample_power_management_response, timestamp


@pytest.fixture
def sample_power_management_response_multiple_with_timestamp(
    sample_power_management_response_multiple: list[PowerManagementInfo],
    tzinfo: datetime.tzinfo
) -> list[WithTimeStamp[PowerManagementInfo]]:
    base_time = datetime.datetime(2024, 1, 1, 12, 0, tzinfo=tzinfo)
    return [
        (response, base_time + datetime.timedelta(minutes=i*5))
        for i, response in enumerate(sample_power_management_response_multiple)
    ]


@pytest.fixture
def sample_base_unit_status(
    sample_base_unit_info: BaseUnitInfo,
    tzinfo: datetime.tzinfo
) -> BaseUnitStatus:
    return BaseUnitStatus(
        base_unit=sample_base_unit_info,
        current_uptime=datetime.timedelta(hours=1),
        total_uptime=datetime.timedelta(days=10),
        error_code="Ok",
        error_message=None,
        first_used=datetime.datetime(2024, 1, 1, 2, 3, tzinfo=tzinfo),
        in_use=False,
        sharing=False,
    )

@pytest.fixture
def sample_base_unit_status_multiple(
    sample_base_unit_status: BaseUnitStatus,
) -> list[BaseUnitStatus]:
    """Fixture that provides multiple BaseUnitStatus objects with different
    uptimes and sharing statuses
    """
    return [
        sample_base_unit_status,
        BaseUnitStatus(
            base_unit=sample_base_unit_status.base_unit,
            current_uptime=sample_base_unit_status.current_uptime + datetime.timedelta(hours=1),
            total_uptime=sample_base_unit_status.total_uptime + datetime.timedelta(hours=1),
            error_code="Ok",
            error_message=None,
            first_used=sample_base_unit_status.first_used,
            in_use=True,
            sharing=True,
        ),
    ]


@pytest.fixture
def sample_base_unit_usage_status(
    sample_base_unit_info: BaseUnitInfo
) -> BaseUnitUsageStatus:
    return BaseUnitUsageStatus(
        base_unit=sample_base_unit_info,
        in_use=True,
        sharing=True,
    )

@pytest.fixture
def sample_base_unit_usage_status_multiple(
    sample_base_unit_usage_status: BaseUnitUsageStatus,
) -> list[BaseUnitUsageStatus]:
    """Fixture that provides multiple BaseUnitUsageStatus objects with different usage statuses
    """
    return [
        sample_base_unit_usage_status,
        BaseUnitUsageStatus(
            base_unit=sample_base_unit_usage_status.base_unit,
            in_use=False,
            sharing=False,
        ),
    ]


@pytest.fixture
def sample_base_unit_usage_status_with_timestamp(
    sample_base_unit_usage_status: BaseUnitUsageStatus,
    tzinfo: datetime.tzinfo
) -> WithTimeStamp[BaseUnitUsageStatus]:
    timestamp = datetime.datetime(2024, 1, 1, 12, 0, tzinfo=tzinfo)
    return sample_base_unit_usage_status, timestamp


@pytest.fixture
def sample_base_unit_usage_status_multiple_with_timestamp(
    sample_base_unit_usage_status_multiple: list[BaseUnitUsageStatus],
    tzinfo: datetime.tzinfo
) -> list[WithTimeStamp[BaseUnitUsageStatus]]:
    base_time = datetime.datetime(2024, 1, 1, 12, 0, tzinfo=tzinfo)
    return [
        (status, base_time + datetime.timedelta(minutes=i*5))
        for i, status in enumerate(sample_base_unit_usage_status_multiple)
    ]


@pytest.fixture
def sample_base_unit_status_with_timestamp(
    sample_base_unit_status: BaseUnitStatus,
    tzinfo: datetime.tzinfo
) -> WithTimeStamp[BaseUnitStatus]:
    reading_time = datetime.datetime(2024, 1, 1, 12, 0, tzinfo=tzinfo)
    return sample_base_unit_status, reading_time


@pytest.fixture
def sample_base_unit_status_multiple_with_timestamp(
    sample_base_unit_status_multiple: list[BaseUnitStatus],
    tzinfo: datetime.tzinfo
) -> list[WithTimeStamp[BaseUnitStatus]]:
    base_time = datetime.datetime(2024, 1, 1, 12, 0, tzinfo=tzinfo)
    return [
        (status, base_time + datetime.timedelta(minutes=i*5))
        for i, status in enumerate(sample_base_unit_status_multiple)
    ]

@pytest.fixture
def sample_sensor_reading(tzinfo: datetime.tzinfo) -> SensorReading:
    return SensorReading(
        timestamp=datetime.datetime(2024, 1, 1, 12, 0, 0, tzinfo=tzinfo),
        sensor="CPU",
        value=50.0,
    )


@pytest.fixture
def sample_temperature_history_with_serialized_lines(
    tzinfo: datetime.tzinfo,
    sample_base_unit_info: BaseUnitInfo
) -> tuple[TemperatureHistory, list[str]]:
    dt = datetime.datetime(2024, 1, 1, 12, 8, 4, tzinfo=tzinfo)
    readings: list[tuple[SensorReading, str]] = [
        (
                SensorReading(
                timestamp=dt,
                sensor="CPU",
                value=50.0,
            ),
            f"{dt.isoformat()} CPU 50.00°C"
        ),
        (
            SensorReading(
                timestamp=dt,
                sensor="WLAN0",
                value=45.0,
            ),
            f"{dt.isoformat()} WLAN0 45.00°C"
        ),
        (
            SensorReading(
                timestamp=dt,
                sensor="WLAN1",
                value=47.5,
            ),
            f"{dt.isoformat()} WLAN1 47.50°C"
        ),
        (
            SensorReading(
                timestamp=dt + datetime.timedelta(minutes=5),
                sensor="CPU",
                value=55.0,
            ),
            f"{(dt + datetime.timedelta(minutes=5)).isoformat()} CPU 55.00°C"
        ),
        (
            SensorReading(
                timestamp=dt + datetime.timedelta(minutes=5),
                sensor="WLAN0",
                value=46.0,
            ),
            f"{(dt + datetime.timedelta(minutes=5)).isoformat()} WLAN0 46.00°C"
        ),
        (
            SensorReading(
                timestamp=dt + datetime.timedelta(minutes=5),
                sensor="WLAN1",
                value=48.0,
            ),
            f"{(dt + datetime.timedelta(minutes=5)).isoformat()} WLAN1 48.00°C"
        ),
    ]
    return (
        TemperatureHistory(
            base_unit=sample_base_unit_info,
            readings=[r for r, _ in readings]
        ),
        [s for _, s in readings]
    )


@pytest.fixture
def sample_temperature_history(
    sample_temperature_history_with_serialized_lines: tuple[TemperatureHistory, list[str]]
) -> TemperatureHistory:
    return sample_temperature_history_with_serialized_lines[0]
