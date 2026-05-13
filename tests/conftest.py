
import datetime
from zoneinfo import ZoneInfo

import pytest

from clickshare_temperature.types import (
    BaseUnitInfo,
    BaseUnitIdentity,
    BaseUnitStatus,
    BaseUnitUsageStatus,
    PowerManagementInfo,
)
from clickshare_temperature.temperature_history import TemperatureHistory, SensorReading

type WithTimeStamp[T] = tuple[T, datetime.datetime]

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
def sample_power_management_response_with_timestamp(
    sample_power_management_response,
    tzinfo: datetime.tzinfo
) -> WithTimeStamp[PowerManagementInfo]:
    timestamp = datetime.datetime(2024, 1, 1, 12, 0, tzinfo=tzinfo)
    return sample_power_management_response, timestamp

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
def sample_base_unit_usage_status(
    sample_base_unit_info: BaseUnitInfo
) -> BaseUnitUsageStatus:
    return BaseUnitUsageStatus(
        base_unit=sample_base_unit_info,
        in_use=True,
        sharing=True,
    )

@pytest.fixture
def sample_base_unit_usage_status_with_timestamp(
    sample_base_unit_usage_status: BaseUnitUsageStatus,
    tzinfo: datetime.tzinfo
) -> WithTimeStamp[BaseUnitUsageStatus]:
    timestamp = datetime.datetime(2024, 1, 1, 12, 0, tzinfo=tzinfo)
    return sample_base_unit_usage_status, timestamp



@pytest.fixture
def sample_base_unit_status_with_timestamp(
    sample_base_unit_status: BaseUnitStatus,
    tzinfo: datetime.tzinfo
) -> WithTimeStamp[BaseUnitStatus]:
    reading_time = datetime.datetime(2024, 1, 1, 12, 0, tzinfo=tzinfo)
    return sample_base_unit_status, reading_time


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
