import pytest
from typing import Callable, NamedTuple
import datetime
from pathlib import Path
import json

from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, IntegrityError, NoResultFound

from clickshare_temperature.orm import (
    set_engine_uri,
    get_engine_uri,
    init_db,
    get_session,
    BaseUnit as BaseUnitModel,
    BaseUnitIdentity as BaseUnitIdentityModel,
    BaseUnitOnlineStatus as BaseUnitOnlineStatusModel,
    PowerManagementSettings as PowerManagementSettingsModel,
    PowerManagementStatus as PowerManagementStatusModel,
    BaseUnitStatus as BaseUnitStatusModel,
    BaseUnitUsageStatus as BaseUnitUsageStatusModel,
    SensorReading as SensorReadingModel,
)
from clickshare_temperature.orm.serialization import (
    SERIALIZATION_VERSION,
    SerializationFormatV0,
    SerializationFormatV1,
    serialize_database,
    deserialize_database,
)
from clickshare_temperature.orm.cli import get_online_statuses_for_influx_backfill
from clickshare_temperature.temperature_history import TemperatureHistory, SensorReading
from clickshare_temperature.types import (
    BaseUnitIdentity,
    BaseUnitInfo,
    BaseUnitStatus,
    BaseUnitUsageStatus,
    PowerManagementInfo,
    SensorType,
)

from .conftest import _reset_engine

type WithTimeStamp[T] = tuple[T, datetime.datetime]




@pytest.fixture
def sample_base_unit_model(
    sample_base_unit_info: BaseUnitInfo,
    db_session
) -> BaseUnitModel:
    base_unit = BaseUnitModel.from_info(sample_base_unit_info)
    db_session.add(base_unit)
    db_session.commit()
    return base_unit


@pytest.fixture
def base_unit_factory(db_session: Session) -> Callable[[str], BaseUnitModel]:
    """Create and persist uniquely named BaseUnit models for query tests

    The suffix parameter is used to generate distinct hostnames and room names
    so tests can create multiple BaseUnits without violating unique constraints.

    """
    def _factory(suffix: str) -> BaseUnitModel:
        """Build one persisted BaseUnit using the provided suffix"""
        base_unit = BaseUnitModel(
            hostname=f"test-baseunit-{suffix}",
            room_name=f"Test Room {suffix}",
            ip_address=f"192.168.1.{(abs(hash(suffix)) % 200) + 10}",
        )
        db_session.add(base_unit)
        db_session.commit()
        return base_unit

    return _factory


@pytest.fixture
def sample_base_unit_status_model(
    sample_base_unit_status: BaseUnitStatus,
    sample_base_unit_model: BaseUnitModel,
    db_session
) -> BaseUnitStatusModel:
    status = BaseUnitStatusModel.from_data(sample_base_unit_model, sample_base_unit_status)
    db_session.add(status)
    db_session.commit()
    return status

@pytest.fixture
def sample_base_unit_usage_status_model(
    sample_base_unit_usage_status: BaseUnitUsageStatus,
    sample_base_unit_model: BaseUnitModel,
    tzinfo: datetime.tzinfo,
    db_session
) -> WithTimeStamp[BaseUnitUsageStatusModel]:
    timestamp = datetime.datetime(2024, 1, 1, 12, 0, tzinfo=tzinfo)
    usage_status = BaseUnitUsageStatusModel.from_data(
        sample_base_unit_model,
        sample_base_unit_usage_status,
        now=timestamp,
    )
    db_session.add(usage_status)
    db_session.commit()
    return usage_status, timestamp

@pytest.fixture
def sample_sensor_reading_model(
    sample_sensor_reading: SensorReading,
    sample_base_unit_model: BaseUnitModel,
    db_session
) -> SensorReadingModel:
    reading_model = SensorReadingModel.from_data(
        sample_base_unit_model, sample_sensor_reading, db_session
    )
    db_session.add(reading_model)
    db_session.commit()
    return reading_model

@pytest.fixture
def sample_sensor_history_models(
    sample_temperature_history: TemperatureHistory,
    sample_base_unit_model: BaseUnitModel,
    db_session
) -> list[SensorReadingModel]:
    models = []
    for reading in sample_temperature_history.readings:
        model = SensorReadingModel.from_data(sample_base_unit_model, reading, db_session)
        db_session.add(model)
        models.append(model)
    db_session.commit()
    return models

class FullyPopulatedDBData(NamedTuple):
    base_unit: BaseUnitInfo
    identity: BaseUnitIdentity
    power_management_responses: list[WithTimeStamp[PowerManagementInfo]]
    base_unit_statuses: list[WithTimeStamp[BaseUnitStatus]]
    base_unit_usage_statuses: list[WithTimeStamp[BaseUnitUsageStatus]]
    temperature_history: TemperatureHistory

@pytest.fixture
def fully_populated_db_data(
    sample_base_unit_info: BaseUnitInfo,
    sample_base_unit_identity: BaseUnitIdentity,
    sample_power_management_response_multiple_with_timestamp: list[WithTimeStamp[PowerManagementInfo]],
    sample_base_unit_status_multiple_with_timestamp: list[WithTimeStamp[BaseUnitStatus]],
    sample_base_unit_usage_status_multiple_with_timestamp: list[WithTimeStamp[BaseUnitUsageStatus]],
    sample_temperature_history: TemperatureHistory
) -> FullyPopulatedDBData:
    return FullyPopulatedDBData(
        base_unit=sample_base_unit_info,
        identity=sample_base_unit_identity,
        power_management_responses=sample_power_management_response_multiple_with_timestamp,
        base_unit_statuses=sample_base_unit_status_multiple_with_timestamp,
        base_unit_usage_statuses=sample_base_unit_usage_status_multiple_with_timestamp,
        temperature_history=sample_temperature_history
    )


@pytest.fixture
def fully_populated_db_session(
    db_session,
    fully_populated_db_data: FullyPopulatedDBData,
    tzinfo: datetime.tzinfo,
) -> Session:
    _populate_db_with_data(db_session, fully_populated_db_data)
    return db_session


def _populate_db_with_data(
    db_session: Session,
    fully_populated_db_data: FullyPopulatedDBData,
) -> None:
    src_data = fully_populated_db_data
    base_unit_info = src_data.base_unit
    base_unit = BaseUnitModel.from_info(base_unit_info)
    db_session.add(base_unit)
    db_session.commit()

    identity = BaseUnitIdentityModel.from_data(base_unit, src_data.identity, db_session)
    db_session.add(identity)

    latest_power_status = max(
        src_data.power_management_responses,
        key=lambda item: item[1],
        default=None,
    )
    assert latest_power_status is not None
    power_settings_data, _ = latest_power_status
    power_settings_model = PowerManagementSettingsModel.from_data(
        base_unit,
        power_settings_data,
        session=db_session,
    )
    db_session.add(power_settings_model)

    for power_status_data, power_status_timestamp in src_data.power_management_responses:
        power_status_model = PowerManagementStatusModel.from_data(
            base_unit,
            power_status_data,
            now=power_status_timestamp,
        )
        db_session.add(power_status_model)

    for status_data, status_timestamp in src_data.base_unit_statuses:
        status_model = BaseUnitStatusModel.from_data(
            base_unit,
            status_data,
            now=status_timestamp,
        )
        db_session.add(status_model)

    for usage_status_data, usage_status_timestamp in src_data.base_unit_usage_statuses:
        usage_status_model = BaseUnitUsageStatusModel.from_data(
            base_unit,
            usage_status_data,
            now=usage_status_timestamp,
        )
        db_session.add(usage_status_model)
    db_session.commit()

    readings = src_data.temperature_history.readings

    num_added, num_skipped = base_unit.add_sensor_readings(readings, session=db_session)
    assert num_added == len(readings)
    assert num_skipped == 0
    db_session.commit()




def test_db_is_uninitialized(uninitialized_db):
    with pytest.raises(OperationalError):
        with get_session() as session:
            _ = session.query(BaseUnitModel).first()


def test_base_unit_get_by_hostname(
    db_session: Session,
    sample_base_unit_info: BaseUnitInfo,
    sample_base_unit_model: BaseUnitModel,
) -> None:
    """Test the `get_by_hostname` method and ensure its exceptions are raised
    as expected
    """
    retrieved = BaseUnitModel.get_by_hostname(
        sample_base_unit_info.hostname, session=db_session,
    )
    assert retrieved is not None
    retrieved_2 = BaseUnitModel.get_by_hostname(
        sample_base_unit_info.hostname, session=db_session, raise_if_absent=True
    )
    assert retrieved_2 is retrieved is sample_base_unit_model

    with pytest.raises(NoResultFound):
        BaseUnitModel.get_by_hostname("abcdef", session=db_session, raise_if_absent=True)


def test_base_unit_model_unique_constraints(db_session):
    base_unit_info = BaseUnitInfo(
        hostname="test-baseunit",
        room_name="Test Room",
        ip_address="192.168.1.1",
    )
    base_unit = BaseUnitModel(
        hostname=base_unit_info.hostname,
        room_name=base_unit_info.room_name,
        ip_address=base_unit_info.ip_address,
    )
    db_session.add(base_unit)
    db_session.commit()

    # Attempt to add another BaseUnit with the same hostname
    duplicate_hostname = BaseUnitModel(
        hostname=base_unit_info.hostname,
        room_name="Another Room",
        ip_address="192.168.1.2",
    )
    db_session.add(duplicate_hostname)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_base_unit_status_model_unique_constraints(
    db_session,
    sample_base_unit_info: BaseUnitInfo,
    sample_base_unit_status: BaseUnitStatus
) -> None:
    base_unit = BaseUnitModel(
        hostname=sample_base_unit_info.hostname,
        room_name=sample_base_unit_info.room_name,
        ip_address=sample_base_unit_info.ip_address,
    )
    db_session.add(base_unit)
    db_session.commit()

    assert base_unit.id is not None

    status_timestamp = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)

    status = BaseUnitStatusModel(
        base_unit_id=base_unit.id,
        timestamp=status_timestamp,
        current_uptime=int(sample_base_unit_status.current_uptime.total_seconds()),
        total_uptime=int(sample_base_unit_status.total_uptime.total_seconds()),
        error_code=sample_base_unit_status.error_code,
        error_message=sample_base_unit_status.error_message,
        first_used=sample_base_unit_status.first_used,
        in_use=sample_base_unit_status.in_use,
        sharing=sample_base_unit_status.sharing,
    )
    db_session.add(status)
    db_session.commit()

    assert base_unit.statuses[0].timestamp == status_timestamp

    # Attempt to add another BaseUnitStatus with the same base_unit_id and timestamp
    duplicate_status = BaseUnitStatusModel(
        base_unit_id=base_unit.id,
        timestamp=status_timestamp,
        current_uptime=int(sample_base_unit_status.current_uptime.total_seconds()),
        total_uptime=int(sample_base_unit_status.total_uptime.total_seconds()),
        error_code="AnotherError",
        error_message="Another error message",
        first_used=sample_base_unit_status.first_used,
        in_use=True,
        sharing=True,
    )
    db_session.add(duplicate_status)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_sensor_reading_unique_constraints(db_session, sample_base_unit_info: BaseUnitInfo) -> None:
    base_unit = BaseUnitModel(
        hostname=sample_base_unit_info.hostname,
        room_name=sample_base_unit_info.room_name,
        ip_address=sample_base_unit_info.ip_address,
    )
    db_session.add(base_unit)
    db_session.commit()



    reading_data = SensorReading[SensorType](
        timestamp=datetime.datetime(2024, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc),
        sensor="CPU",
        value=50.0,
    )

    base_unit.add_sensor_reading(reading_data, session=db_session)
    db_session.commit()

    assert base_unit.id is not None
    assert len(base_unit.sensor_readings) == 1
    assert base_unit.sensor_readings[0].timestamp == reading_data.timestamp
    assert base_unit.sensor_readings[0].sensor_type == reading_data.sensor
    assert base_unit.sensor_readings[0].value == reading_data.value

    # Attempt to add another SensorReading with the same base_unit_id, timestamp, and sensor
    duplicate_reading = SensorReadingModel(
        base_unit_id=base_unit.id,
        timestamp=datetime.datetime(2024, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc),
        sensor_type="CPU",
        value=55.0,
    )
    db_session.add(duplicate_reading)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_base_unit_from_info(
    db_session,
    sample_base_unit_info: BaseUnitInfo
) -> None:
    base_unit = BaseUnitModel.from_info(sample_base_unit_info)
    db_session.add(base_unit)
    db_session.commit()

    assert base_unit.hostname == sample_base_unit_info.hostname
    assert base_unit.room_name == sample_base_unit_info.room_name
    assert base_unit.ip_address == sample_base_unit_info.ip_address

def test_base_unit_status_from_status(
    db_session,
    sample_base_unit_info: BaseUnitInfo,
    sample_base_unit_status: BaseUnitStatus
) -> None:
    base_unit = BaseUnitModel.from_info(sample_base_unit_info)
    db_session.add(base_unit)
    db_session.commit()

    status = BaseUnitStatusModel.from_data(base_unit, sample_base_unit_status)
    db_session.add(status)
    db_session.commit()

    status = db_session.query(BaseUnitStatusModel).where(
        BaseUnitStatusModel.base_unit_id == base_unit.id
    ).one()

    assert status.base_unit_id == base_unit.id
    assert status.current_uptime == int(sample_base_unit_status.current_uptime.total_seconds())
    assert status.total_uptime == int(sample_base_unit_status.total_uptime.total_seconds())
    assert status.error_code == sample_base_unit_status.error_code
    assert status.error_message == sample_base_unit_status.error_message
    assert status.first_used == sample_base_unit_status.first_used



def test_sensor_reading_from_data(
    db_session,
    sample_base_unit_info: BaseUnitInfo,
    sample_sensor_reading: SensorReading
) -> None:
    base_unit = BaseUnitModel.from_info(sample_base_unit_info)
    db_session.add(base_unit)
    db_session.commit()

    reading_model = SensorReadingModel.from_data(base_unit, sample_sensor_reading, db_session)
    db_session.add(reading_model)
    db_session.commit()

    assert reading_model.base_unit_id == base_unit.id
    assert reading_model.timestamp == sample_sensor_reading.timestamp
    assert reading_model.sensor_type == sample_sensor_reading.sensor
    assert reading_model.value == sample_sensor_reading.value


def test_base_unit_to_info(
    sample_base_unit_model: BaseUnitModel,
    sample_base_unit_info: BaseUnitInfo
) -> None:
    info = sample_base_unit_model.to_data()
    assert info == sample_base_unit_info

def test_base_unit_status_to_status(
    sample_base_unit_status_model: BaseUnitStatusModel,
    sample_base_unit_status: BaseUnitStatus
) -> None:
    status = sample_base_unit_status_model.to_data()
    assert status == sample_base_unit_status

def test_sensor_reading_to_reading(sample_sensor_reading_model: SensorReadingModel) -> None:
    reading = sample_sensor_reading_model.to_data()
    assert reading.timestamp == sample_sensor_reading_model.timestamp
    assert reading.sensor == sample_sensor_reading_model.sensor_type
    assert reading.value == sample_sensor_reading_model.value


def test_base_unit_add_multiple_sensor_readings(
    db_session,
    sample_base_unit_info: BaseUnitInfo,
    sample_temperature_history: TemperatureHistory
) -> None:
    base_unit = BaseUnitModel.from_info(sample_base_unit_info)
    db_session.add(base_unit)
    db_session.commit()

    num_added, num_skipped = base_unit.add_sensor_readings(sample_temperature_history.readings, session=db_session)
    assert num_added == len(sample_temperature_history.readings)
    assert num_skipped == 0
    db_session.commit()

    persisted = sorted(base_unit.sensor_readings, key=lambda r: (r.timestamp, r.sensor_type))
    expected = sorted(sample_temperature_history.readings, key=lambda r: (r.timestamp, r.sensor))
    assert len(persisted) == len(expected)
    for reading_model, reading_data in zip(persisted, expected, strict=True):
        assert reading_model.timestamp == reading_data.timestamp
        assert reading_model.sensor_type == reading_data.sensor
        assert reading_model.value == reading_data.value
        assert reading_model.to_data() == reading_data


def test_sensor_reading_round_trip(
    db_session,
    sample_base_unit_info: BaseUnitInfo,
    sample_temperature_history_with_serialized_lines: tuple[TemperatureHistory, list[str]],
    tzinfo: datetime.tzinfo
) -> None:
    temperature_history, serialized_lines = sample_temperature_history_with_serialized_lines

    base_unit = BaseUnitModel.from_info(sample_base_unit_info)
    db_session.add(base_unit)
    db_session.commit()

    num_added, num_skipped = base_unit.add_sensor_readings(temperature_history.readings, session=db_session)
    assert num_added == len(temperature_history.readings)
    assert num_skipped == 0
    db_session.commit()

    persisted = sorted(base_unit.sensor_readings, key=lambda r: (r.timestamp, r.sensor_type))
    expected = sorted(
        zip(temperature_history.readings, serialized_lines, strict=True),
        key=lambda item: (item[0].timestamp, item[0].sensor),
    )
    assert len(persisted) == len(expected)
    for reading_model, (reading_data, line_str) in zip(persisted, expected, strict=True):
        assert reading_model.timestamp == reading_data.timestamp
        assert reading_model.sensor_type == reading_data.sensor
        assert reading_model.value == reading_data.value
        reading = reading_model.to_data()
        assert reading == reading_data
        assert reading.as_timezone(tzinfo).serialize_str() == line_str


def test_get_online_statuses_for_influx_backfill_selection(
    db_session: Session,
    base_unit_factory: Callable[[str], BaseUnitModel],
) -> None:
    """Select unuploaded rows plus stale/missing latest per BaseUnit

    This validates the intended dual-branch behavior:

    1. Any row with uploaded_to_influx=False is always selected.
    2. The latest row per BaseUnit is selected when last_upload_to_influx is
       missing or outside the configured time window.

    """
    now = datetime.datetime(2024, 1, 1, 12, 0, tzinfo=datetime.timezone.utc)
    window = datetime.timedelta(hours=1)

    base_unit_a = base_unit_factory("a")
    base_unit_b = base_unit_factory("b")
    base_unit_c = base_unit_factory("c")

    status_a_old_unuploaded = BaseUnitOnlineStatusModel(
        base_unit_id=base_unit_a.id,
        timestamp=now - datetime.timedelta(hours=3),
        online=True,
        uploaded_to_influx=False,
        last_upload_to_influx=now - datetime.timedelta(minutes=5),
    )
    status_a_latest_recent = BaseUnitOnlineStatusModel(
        base_unit_id=base_unit_a.id,
        timestamp=now - datetime.timedelta(minutes=30),
        online=True,
        uploaded_to_influx=True,
        last_upload_to_influx=now - datetime.timedelta(minutes=5),
    )
    status_b_latest_stale = BaseUnitOnlineStatusModel(
        base_unit_id=base_unit_b.id,
        timestamp=now - datetime.timedelta(minutes=20),
        online=False,
        uploaded_to_influx=True,
        last_upload_to_influx=now - datetime.timedelta(hours=2),
    )
    status_c_latest_missing_upload_ts = BaseUnitOnlineStatusModel(
        base_unit_id=base_unit_c.id,
        timestamp=now - datetime.timedelta(minutes=10),
        online=True,
        uploaded_to_influx=True,
        last_upload_to_influx=None,
    )

    db_session.add_all([
        status_a_old_unuploaded,
        status_a_latest_recent,
        status_b_latest_stale,
        status_c_latest_missing_upload_ts,
    ])
    db_session.commit()

    stmt = get_online_statuses_for_influx_backfill(
        db_session,
        time_series_window=window,
        now=now,
    )
    results = db_session.execute(stmt).scalars().all()

    result_ids = {status.id for status in results}
    expected_ids = {
        status_a_old_unuploaded.id,
        status_b_latest_stale.id,
        status_c_latest_missing_upload_ts.id,
    }

    assert result_ids == expected_ids
    assert status_a_latest_recent.id not in result_ids



def test_base_unit_identity_get_by_natural_key(
    db_session: Session,
    sample_base_unit_info: BaseUnitInfo,
    sample_base_unit_identity: BaseUnitIdentity,
) -> None:
    base_unit = BaseUnitModel.from_info(sample_base_unit_info)
    db_session.add(base_unit)
    db_session.commit()

    identity_model = BaseUnitIdentityModel.from_data(base_unit, sample_base_unit_identity, db_session)
    db_session.add(identity_model)
    db_session.commit()

    natural_key = identity_model.natural_key
    retrieved = BaseUnitIdentityModel.get_by_natural_key(db_session, natural_key)
    assert retrieved is not None
    assert retrieved.id == identity_model.id
    assert retrieved.base_unit_id == identity_model.base_unit_id == base_unit.id
    assert retrieved.to_data() == identity_model.to_data() == sample_base_unit_identity



def test_power_settings_get_by_natural_key(
    db_session: Session,
    sample_base_unit_info: BaseUnitInfo,
    sample_power_management_response: PowerManagementInfo,
) -> None:
    base_unit = BaseUnitModel.from_info(sample_base_unit_info)
    db_session.add(base_unit)
    db_session.commit()

    settings = PowerManagementSettingsModel.from_data(
        base_unit,
        sample_power_management_response,
        session=db_session,
    )
    db_session.add(settings)
    db_session.commit()

    natural_key = settings.natural_key
    retrieved = PowerManagementSettingsModel.get_by_natural_key(db_session, natural_key)
    assert retrieved is not None
    assert retrieved.id == settings.id
    assert retrieved.base_unit_id == settings.base_unit_id == base_unit.id
    assert retrieved.mode == settings.mode == sample_power_management_response.power_mode
    assert retrieved.standby_timeout == settings.standby_timeout == sample_power_management_response.standby_timeout_minutes


def test_power_management_status_get_by_natural_key(
    db_session: Session,
    sample_base_unit_info: BaseUnitInfo,
    sample_power_management_response_multiple_with_timestamp: list[WithTimeStamp[PowerManagementInfo]],
) -> None:
    src_data = sample_power_management_response_multiple_with_timestamp
    base_unit = BaseUnitModel.from_info(sample_base_unit_info)
    db_session.add(base_unit)
    db_session.commit()

    for power_status_data, power_status_timestamp in src_data:
        power_status_model = PowerManagementStatusModel.from_data(
            base_unit,
            power_status_data,
            now=power_status_timestamp,
        )
        db_session.add(power_status_model)
    db_session.commit()

    persisted_models = sorted(base_unit.power_management_statuses, key=lambda s: s.timestamp)
    expected_data = sorted(src_data, key=lambda item: item[1])
    assert len(persisted_models) == len(expected_data)
    for model, (data, timestamp) in zip(persisted_models, expected_data, strict=True):
        natural_key = model.natural_key
        retrieved = PowerManagementStatusModel.get_by_natural_key(db_session, natural_key)
        assert retrieved is not None
        assert retrieved.id == model.id
        assert retrieved.base_unit_id == model.base_unit_id == base_unit.id
        assert retrieved.timestamp == model.timestamp == timestamp
        assert retrieved.power_mode_status == model.power_mode_status == data.status


def test_base_unit_status_get_by_natural_key(
    db_session: Session,
    sample_base_unit_info: BaseUnitInfo,
    sample_base_unit_status_multiple_with_timestamp: list[WithTimeStamp[BaseUnitStatus]],
) -> None:
    src_data = sample_base_unit_status_multiple_with_timestamp
    base_unit = BaseUnitModel.from_info(sample_base_unit_info)
    db_session.add(base_unit)
    db_session.commit()

    for status_data, status_timestamp in src_data:
        status_model = BaseUnitStatusModel.from_data(
            base_unit,
            status_data,
            now=status_timestamp,
        )
        db_session.add(status_model)
    db_session.commit()

    persisted_models = sorted(base_unit.statuses, key=lambda s: s.timestamp)
    expected_data = sorted(src_data, key=lambda item: item[1])
    assert len(persisted_models) == len(expected_data)
    for model, (data, timestamp) in zip(persisted_models, expected_data, strict=True):
        natural_key = model.natural_key
        retrieved = BaseUnitStatusModel.get_by_natural_key(db_session, natural_key)
        assert retrieved is not None
        assert retrieved.id == model.id
        assert retrieved.base_unit_id == model.base_unit_id == base_unit.id
        assert retrieved.timestamp == model.timestamp == timestamp
        assert retrieved.to_data() == model.to_data() == data


def test_base_unit_usage_status_get_by_natural_key(
    db_session: Session,
    sample_base_unit_info: BaseUnitInfo,
    sample_base_unit_usage_status_multiple_with_timestamp: list[WithTimeStamp[BaseUnitUsageStatus]],
) -> None:
    src_data = sample_base_unit_usage_status_multiple_with_timestamp
    base_unit = BaseUnitModel.from_info(sample_base_unit_info)
    db_session.add(base_unit)
    db_session.commit()

    for usage_status_data, usage_status_timestamp in src_data:
        usage_status_model = BaseUnitUsageStatusModel.from_data(
            base_unit,
            usage_status_data,
            now=usage_status_timestamp,
        )
        db_session.add(usage_status_model)
    db_session.commit()

    persisted_models = sorted(base_unit.usage_statuses, key=lambda s: s.timestamp)
    expected_data = sorted(src_data, key=lambda item: item[1])
    assert len(persisted_models) == len(expected_data)
    for model, (data, timestamp) in zip(persisted_models, expected_data, strict=True):
        natural_key = model.natural_key
        retrieved = BaseUnitUsageStatusModel.get_by_natural_key(db_session, natural_key)
        assert retrieved is not None
        assert retrieved.id == model.id
        assert retrieved.base_unit_id == model.base_unit_id == base_unit.id
        assert retrieved.timestamp == model.timestamp == timestamp
        assert retrieved.to_data() == model.to_data() == data


def test_sensor_reading_get_by_natural_key(
    db_session: Session,
    sample_base_unit_info: BaseUnitInfo,
    sample_temperature_history: TemperatureHistory
) -> None:
    base_unit = BaseUnitModel.from_info(sample_base_unit_info)
    db_session.add(base_unit)
    db_session.commit()

    num_added, num_skipped = base_unit.add_sensor_readings(
        sample_temperature_history.readings,
        session=db_session,
    )
    assert num_added == len(sample_temperature_history.readings)
    assert num_skipped == 0
    db_session.commit()

    persisted_models = sorted(base_unit.sensor_readings, key=lambda r: (r.timestamp, r.sensor_type))
    expected_data = sorted(sample_temperature_history.readings, key=lambda r: (r.timestamp, r.sensor))
    assert len(persisted_models) == len(expected_data)
    for model, data in zip(persisted_models, expected_data, strict=True):
        assert model.to_data() == data
        natural_key = model.natural_key
        retrieved = SensorReadingModel.get_by_natural_key(db_session, natural_key)
        assert retrieved is not None
        assert retrieved.id == model.id
        assert retrieved.base_unit_id == model.base_unit_id == base_unit.id
        assert retrieved.to_data() == data



def test_fully_populated_db_data(
    fully_populated_db_data: FullyPopulatedDBData,
    db_session: Session,
) -> None:
    """Test that the fully populated DB data can be correctly added to the database
    and retrieved, and that the retrieved data matches the source data
    """
    _populate_db_with_data(db_session, fully_populated_db_data)
    check_fully_populated_db_data(fully_populated_db_data, db_session)


def test_database_deserialization(
    fully_populated_db_data: FullyPopulatedDBData,
    db_session: Session,
    tmp_path: Path,
) -> None:

    # Phase 1: Serialize the database with data, then reset the engine to simulate a fresh start
    _populate_db_with_data(db_session, fully_populated_db_data)
    db_session.commit()
    serialized_db_json = serialize_database(db_session)
    db_session.close()
    _reset_engine()


    # Phase 2: Initialize a new database and deserialize the data into it,
    # then verify the data was correctly deserialized
    db_file = tmp_path / "deserialized.db"
    assert not db_file.exists()
    new_uri = f"sqlite:///{db_file}"
    set_engine_uri(new_uri)
    assert str(get_engine_uri()) == str(new_uri)
    init_db()
    assert db_file.exists()
    new_db_session = get_session()

    assert new_db_session is not db_session
    db_session = new_db_session

    # Sanity check that the new database is empty before deserialization
    assert db_session.query(BaseUnitModel).count() == 0
    assert db_session.query(BaseUnitStatusModel).count() == 0
    assert db_session.query(SensorReadingModel).count() == 0

    src_data = fully_populated_db_data
    deserialize_database(db_session, serialized_db_json)
    check_fully_populated_db_data(src_data, db_session)


def test_database_deserialization_legacy_list_format(
    fully_populated_db_data: FullyPopulatedDBData,
    db_session: Session,
    tmp_path: Path,
) -> None:
    """Test that the deserialization can handle the legacy list format where
    all models are in a single list without grouping by model type
    """
    # Phase 1: Serialize the database with data, then reset the engine to simulate a fresh start
    _populate_db_with_data(db_session, fully_populated_db_data)
    db_session.commit()
    serialized_db_json = serialize_database(db_session)
    serialized_db_data: SerializationFormatV1 = json.loads(serialized_db_json)
    assert isinstance(serialized_db_data, dict)
    assert serialized_db_data['version'] == SERIALIZATION_VERSION

    # Create a legacy list format by flattening the data into a single list of dicts
    legacy_list_format: SerializationFormatV0 = []
    for model_list in serialized_db_data["data"].values():
        legacy_list_format.extend(model_list)
    legacy_db_json = json.dumps(legacy_list_format)

    db_session.close()
    _reset_engine()

    # Phase 2: Initialize a new database and deserialize the data into it,
    # then verify the data was correctly deserialized
    db_file = tmp_path / "deserialized.db"
    assert not db_file.exists()
    new_uri = f"sqlite:///{db_file}"
    set_engine_uri(new_uri)
    assert str(get_engine_uri()) == str(new_uri)
    init_db()
    assert db_file.exists()
    new_db_session = get_session()

    assert new_db_session is not db_session
    db_session = new_db_session

    # Sanity check that the new database is empty before deserialization
    assert db_session.query(BaseUnitModel).count() == 0
    assert db_session.query(BaseUnitStatusModel).count() == 0
    assert db_session.query(SensorReadingModel).count() == 0

    src_data = fully_populated_db_data
    deserialize_database(db_session, legacy_db_json)
    check_fully_populated_db_data(src_data, db_session)


def check_fully_populated_db_data(src_data: FullyPopulatedDBData, db_session: Session) -> None:
    """Check that the data in the database matches the source data
    """
    base_unit, base_unit_created = BaseUnitModel.get_or_create(
        info=src_data.base_unit, session=db_session,
    )
    assert not base_unit_created
    assert base_unit is not None
    assert base_unit.hostname == src_data.base_unit.hostname
    assert base_unit.room_name == src_data.base_unit.room_name
    assert base_unit.ip_address == src_data.base_unit.ip_address

    assert base_unit.identity.to_data() == src_data.identity

    latest_power_status = max(
        src_data.power_management_responses,
        key=lambda item: item[1],
        default=None,
    )
    assert latest_power_status is not None
    power_settings_data, _ = latest_power_status
    assert base_unit.power_management_settings.mode == power_settings_data.power_mode
    standby_timeout = power_settings_data.standby_timeout_minutes
    assert base_unit.power_management_settings.standby_timeout == standby_timeout

    assert len(base_unit.power_management_statuses) == len(src_data.power_management_responses)

    for power_status_data, power_status_timestamp in src_data.power_management_responses:
        power_status_model = db_session.query(PowerManagementStatusModel).where(
            PowerManagementStatusModel.base_unit_id == base_unit.id,
            PowerManagementStatusModel.timestamp == power_status_timestamp,
        ).one()
        assert power_status_model.power_mode_status == power_status_data.status
        assert power_status_model.timestamp == power_status_timestamp

    assert len(base_unit.statuses) == len(src_data.base_unit_statuses)

    for status_data, status_timestamp in src_data.base_unit_statuses:
        status_model = db_session.query(BaseUnitStatusModel).where(
            BaseUnitStatusModel.base_unit_id == base_unit.id,
            BaseUnitStatusModel.timestamp == status_timestamp,
        ).one()
        assert status_model.base_unit_id == base_unit.id
        assert status_model.current_uptime == int(status_data.current_uptime.total_seconds())
        assert status_model.total_uptime == int(status_data.total_uptime.total_seconds())
        assert status_model.error_code == status_data.error_code
        assert status_model.error_message == status_data.error_message
        assert status_model.first_used == status_data.first_used
        assert status_model.timestamp == status_timestamp

    assert len(base_unit.usage_statuses) == len(src_data.base_unit_usage_statuses)
    for usage_status_data, usage_status_timestamp in src_data.base_unit_usage_statuses:
        usage_status_model = db_session.query(BaseUnitUsageStatusModel).where(
            BaseUnitUsageStatusModel.base_unit_id == base_unit.id,
            BaseUnitUsageStatusModel.timestamp == usage_status_timestamp,
        ).one()
        assert usage_status_model.in_use == usage_status_data.in_use
        assert usage_status_model.sharing == usage_status_data.sharing
        assert usage_status_model.timestamp == usage_status_timestamp

    readings = base_unit.sensor_readings
    assert len(readings) == len(src_data.temperature_history.readings)
    for reading_data in src_data.temperature_history.readings:
        reading_model = db_session.query(SensorReadingModel).where(
            SensorReadingModel.timestamp == reading_data.timestamp,
            SensorReadingModel.sensor_type == reading_data.sensor,
            SensorReadingModel.base_unit_id == base_unit.id,
        ).one()
        assert reading_model.value == reading_data.value
        assert reading_model.to_data() == reading_data

    temp_history = base_unit.to_temperature_history_data(db_session)
    assert temp_history.readings == src_data.temperature_history.readings


def test_temperature_history_from_log_archive_with_sensor_readings(
    db_session: Session,
    log_archive_file: Path,
    log_entry_sensor_readings: list[SensorReading],
) -> None:
    temperature_history = TemperatureHistory.from_archive_file(log_archive_file)
    expected_readings = log_entry_sensor_readings

    base_unit = BaseUnitModel.from_info(temperature_history.base_unit)
    db_session.add(base_unit)
    db_session.commit()

    num_added, num_skipped = base_unit.add_sensor_readings(
        temperature_history.readings,
        session=db_session,
    )
    assert num_added == len(expected_readings)
    assert num_skipped == 0
    db_session.commit()

    persisted = sorted(base_unit.sensor_readings, key=lambda r: (r.timestamp, r.sensor_type))
    expected = sorted(expected_readings, key=lambda r: (r.timestamp, r.sensor))
    assert len(persisted) == len(expected)
    for reading_model, reading_data in zip(persisted, expected, strict=True):
        assert reading_model.timestamp == reading_data.timestamp
        assert reading_model.sensor_type == reading_data.sensor
        assert reading_model.value == reading_data.value
        assert reading_model.to_data() == reading_data
