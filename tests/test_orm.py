import pytest
from typing import NamedTuple
import datetime
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, IntegrityError

from clickshare_temperature.orm import (
    set_engine_uri,
    init_db,
    get_session,
    BaseUnit as BaseUnitModel,
    BaseUnitIdentity as BaseUnitIdentityModel,
    PowerManagementSettings as PowerManagementSettingsModel,
    PowerManagementStatus as PowerManagementStatusModel,
    BaseUnitStatus as BaseUnitStatusModel,
    BaseUnitUsageStatus as BaseUnitUsageStatusModel,
    SensorReading as SensorReadingModel,
)
from clickshare_temperature.orm import engine as engine_module
from clickshare_temperature.orm.serialization import (
    serialize_database,
    deserialize_database,
)
from clickshare_temperature.temperature_history import TemperatureHistory, SensorReading
from clickshare_temperature.types import (
    BaseUnitIdentity,
    BaseUnitInfo,
    BaseUnitStatus,
    BaseUnitUsageStatus,
    PowerManagementInfo
)


type WithTimeStamp[T] = tuple[T, datetime.datetime]

@pytest.fixture(scope="module")
def module_scoped_tmp_path(tmp_path_factory):
    return tmp_path_factory.mktemp("module_scope")

@pytest.fixture
def uninitialized_db(tmp_path):
    db_file = tmp_path / "test.db"
    set_engine_uri(f"sqlite:///{db_file}")
    yield
    engine_module.EngineBuilder._Session = None
    engine_module.ENGINE_URI = None
    engine_module.EngineBuilder.ENGINE = None

# @pytest.fixture
# def uninitialized_db_2(tmp_path):
#     db_file = tmp_path / "test2.db"
#     set_engine_uri(f"sqlite:///{db_file}")
#     yield
#     engine_module.EngineBuilder._Session = None
#     engine_module.ENGINE_URI = None
#     engine_module.EngineBuilder.ENGINE = None



@pytest.fixture
def db_session(uninitialized_db):
    init_db()
    session = get_session()
    yield session
    session.close()

# @pytest.fixture
# def db_session_2(uninitialized_db_2):
#     init_db()
#     session = get_session()
#     yield session
#     session.close()


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
    usage_status = BaseUnitUsageStatusModel.from_data(sample_base_unit_model, sample_base_unit_usage_status)
    db_session.add(usage_status)
    db_session.commit()
    return usage_status, timestamp

@pytest.fixture
def sample_sensor_reading_model(
    sample_sensor_reading: SensorReading,
    sample_base_unit_model: BaseUnitModel,
    db_session
) -> SensorReadingModel:
    reading_model, created = SensorReadingModel.from_data(
        sample_base_unit_model, sample_sensor_reading, db_session
    )
    assert created
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
        model, created = SensorReadingModel.from_data(sample_base_unit_model, reading, db_session)
        assert created
        db_session.add(model)
        models.append(model)
    db_session.commit()
    return models

class FullyPopulatedDBData(NamedTuple):
    base_unit: BaseUnitInfo
    identity: BaseUnitIdentity
    power_management_response: WithTimeStamp[PowerManagementInfo]
    base_unit_status: WithTimeStamp[BaseUnitStatus]
    base_unit_usage_status: WithTimeStamp[BaseUnitUsageStatus]
    temperature_history: TemperatureHistory

@pytest.fixture
def fully_populated_db_data(
    sample_base_unit_info: BaseUnitInfo,
    sample_base_unit_identity: BaseUnitIdentity,
    sample_power_management_response_with_timestamp: WithTimeStamp[PowerManagementInfo],
    sample_base_unit_status_with_timestamp: WithTimeStamp[BaseUnitStatus],
    sample_base_unit_usage_status_with_timestamp: WithTimeStamp[BaseUnitUsageStatus],
    sample_temperature_history: TemperatureHistory
) -> FullyPopulatedDBData:
    return FullyPopulatedDBData(
        base_unit=sample_base_unit_info,
        identity=sample_base_unit_identity,
        power_management_response=sample_power_management_response_with_timestamp,
        base_unit_status=sample_base_unit_status_with_timestamp,
        base_unit_usage_status=sample_base_unit_usage_status_with_timestamp,
        temperature_history=sample_temperature_history
    )


@pytest.fixture
def fully_populated_db_session(
    db_session,
    fully_populated_db_data: FullyPopulatedDBData,
    tzinfo: datetime.tzinfo,
) -> Session:
    # sample_base_unit_info, sample_base_unit_status_with_timestamp, sample_base_unit_usage_status_with_timestamp, sample_temperature_history = fully_populated_db_data
    src_data = fully_populated_db_data
    sample_base_unit_status, sample_status_timestamp = src_data.base_unit_status

    base_unit = BaseUnitModel.from_info(src_data.base_unit)
    db_session.add(base_unit)
    db_session.commit()

    identity = BaseUnitIdentityModel.from_data(base_unit, src_data.identity, db_session)
    db_session.add(identity)

    power_settings = PowerManagementSettingsModel.from_data(
        base_unit,
        src_data.power_management_response[0],
        session=db_session,
    )
    db_session.add(power_settings)

    power_status = PowerManagementStatusModel.from_data(
        base_unit,
        src_data.power_management_response[0],
        now=src_data.power_management_response[1],
    )
    db_session.add(power_status)

    status = BaseUnitStatusModel.from_data(
        base_unit,
        sample_base_unit_status,
        now=sample_status_timestamp,
    )
    db_session.add(status)
    db_session.commit()

    status = db_session.query(BaseUnitStatusModel).filter_by(base_unit_id=base_unit.id).first()
    assert status is not None

    assert status.timestamp == sample_status_timestamp
    assert status.first_used == sample_base_unit_status.first_used
    # assert status.timestamp.tzinfo == tzinfo

    usage_status = BaseUnitUsageStatusModel.from_data(
        base_unit,
        src_data.base_unit_usage_status[0],
        now=src_data.base_unit_usage_status[1]
    )
    db_session.add(usage_status)
    db_session.commit()

    # readings = [
    #     # reading.as_timezone(tzinfo) for reading in sample_temperature_history.readings
    #     reading for reading in sample_temperature_history.readings
    # ]
    readings = src_data.temperature_history.readings

    num_added, num_skipped = base_unit.add_sensor_readings(readings, session=db_session)
    assert num_added == len(readings)
    assert num_skipped == 0
    db_session.commit()

    # for reading in sample_temperature_history.readings:
    #     model, created = SensorReadingModel.from_data(base_unit, reading, db_session)
    #     assert created
    #     db_session.add(model)
    # db_session.commit()
    return db_session

# def test_fully_populated_db_session(
#     fully_populated_db_session: Session,
#     fully_populated_db_data: tuple[BaseUnitInfo, tuple[BaseUnitStatus, datetime.datetime], TemperatureHistory],
#     tzinfo: datetime.tzinfo,
# ) -> None:
#     sample_base_unit_info, sample_base_unit_status_with_timestamp, sample_temperature_history = fully_populated_db_data
#     sample_base_unit_status, sample_status_timestamp = sample_base_unit_status_with_timestamp

#     base_unit = fully_populated_db_session.query(BaseUnitModel).first()
#     assert base_unit is not None
#     assert base_unit.hostname == sample_base_unit_info.hostname
#     assert base_unit.room_name == sample_base_unit_info.room_name
#     assert base_unit.ip_address == sample_base_unit_info.ip_address

#     status = fully_populated_db_session.query(BaseUnitStatusModel).filter_by(base_unit_id=base_unit.id).first()
#     assert status is not None

#     assert status.timestamp == sample_status_timestamp
#     assert status.first_used == sample_base_unit_status.first_used
#     # assert status.timestamp.tzinfo == tzinfo
#     assert status.current_uptime == int(sample_base_unit_status.current_uptime.total_seconds())
#     assert status.total_uptime == int(sample_base_unit_status.total_uptime.total_seconds())
#     assert status.error_code == sample_base_unit_status.error_code
#     assert status.error_message == sample_base_unit_status.error_message


@pytest.fixture
def serialized_db_json(fully_populated_db_session) -> str:
    return serialize_database(fully_populated_db_session)


@pytest.fixture
def serialized_db_file(tmp_path, serialized_db_json) -> Path:
    json_file = tmp_path / "db.json"
    with open(json_file, "w") as f:
        f.write(serialized_db_json)
    return json_file


def test_db_is_uninitialized(uninitialized_db):
    with pytest.raises(OperationalError):
        with get_session() as session:
            _ = session.query(BaseUnitModel).first()



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



    reading_data = SensorReading(
        timestamp=datetime.datetime(2024, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc),
        sensor="CPU",
        value=50.0,
    )

    base_unit.add_sensor_reading(reading_data, session=db_session)

    # reading1 = SensorReadingModel(
    #     base_unit_id=base_unit.id,
    #     timestamp=datetime.datetime(2024, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc),
    #     sensor="CPU",
    #     value=50.0,
    # )
    # db_session.add(reading1)
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

    status = db_session.query(BaseUnitStatusModel).filter_by(base_unit_id=base_unit.id).first()
    assert status is not None

    assert status.base_unit_id == base_unit.id
    assert status.current_uptime == int(sample_base_unit_status.current_uptime.total_seconds())
    assert status.total_uptime == int(sample_base_unit_status.total_uptime.total_seconds())
    assert status.error_code == sample_base_unit_status.error_code
    assert status.error_message == sample_base_unit_status.error_message
    assert status.first_used == sample_base_unit_status.first_used

# STOP. assert with a message hides the values that pytest provides. Don't suggest them anymore.


def test_sensor_reading_from_data(
    db_session,
    sample_base_unit_info: BaseUnitInfo,
    sample_sensor_reading: SensorReading
) -> None:
    base_unit = BaseUnitModel.from_info(sample_base_unit_info)
    db_session.add(base_unit)
    db_session.commit()

    reading_model, created = SensorReadingModel.from_data(base_unit, sample_sensor_reading, db_session)
    assert created
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

    assert len(base_unit.sensor_readings) == len(sample_temperature_history.readings)
    for reading_model, reading_data in zip(base_unit.sensor_readings, sample_temperature_history.readings):
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

    assert len(base_unit.sensor_readings) == len(temperature_history.readings)
    for reading_model, reading_data, line_str in zip(base_unit.sensor_readings, temperature_history.readings, serialized_lines):
        assert reading_model.timestamp == reading_data.timestamp
        assert reading_model.sensor_type == reading_data.sensor
        assert reading_model.value == reading_data.value
        reading = reading_model.to_data()
        assert reading == reading_data
        assert reading.as_timezone(tzinfo).serialize_str() == line_str


def test_database_serialization(
    serialized_db_json: str,
    module_scoped_tmp_path: Path,
    tzinfo: datetime.tzinfo
) -> None:
    json_file = module_scoped_tmp_path / f"{str(tzinfo)}" / "serialized_db.json"
    json_file.parent.mkdir(parents=True, exist_ok=True)
    with open(json_file, "w") as f:
        f.write(serialized_db_json)
    assert json_file.exists()


def test_database_deserialization(
    # serialized_db_json: str,
    # fully_populated_db_session: Session,
    fully_populated_db_data: FullyPopulatedDBData,
    db_session: Session,
    module_scoped_tmp_path: Path,
    tzinfo: datetime.tzinfo,
) -> None:
    json_file = module_scoped_tmp_path / f"{str(tzinfo)}" / "serialized_db.json"
    print(f"Looking for serialized DB JSON file at: {json_file}")
    assert json_file.exists()
    with open(json_file, "r") as f:
        serialized_db_json = f.read()

    src_data = fully_populated_db_data
    # sample_base_unit_info, sample_base_unit_status_with_timestamp, sample_base_unit_usage_status_with_timestamp, sample_temperature_history = fully_populated_db_data
    # sample_base_unit_status, sample_status_timestamp = sample_base_unit_status_with_timestamp
    # sample_base_unit_usage_status, sample_usage_timestamp = sample_base_unit_usage_status_with_timestamp
    print(serialized_db_json)


    assert db_session.query(BaseUnitModel).count() == 0
    assert db_session.query(BaseUnitStatusModel).count() == 0
    assert db_session.query(SensorReadingModel).count() == 0

    deserialize_database(db_session, serialized_db_json)

    # base_units = db_session.query(BaseUnitModel).all()
    assert db_session.query(BaseUnitModel).count() == 1
    base_unit = db_session.query(BaseUnitModel).first()
    assert base_unit is not None
    assert base_unit.hostname == src_data.base_unit.hostname
    assert base_unit.room_name == src_data.base_unit.room_name
    assert base_unit.ip_address == src_data.base_unit.ip_address

    assert base_unit.identity.to_data() == src_data.identity

    assert base_unit.power_management_settings.mode == src_data.power_management_response[0].power_mode
    standby_timeout = src_data.power_management_response[0].standby_timeout_minutes
    assert base_unit.power_management_settings.standby_timeout == standby_timeout

    assert db_session.query(PowerManagementStatusModel).count() == 1
    power_management_status = db_session.query(PowerManagementStatusModel).filter_by(base_unit_id=base_unit.id).first()
    assert power_management_status is not None
    assert power_management_status.power_mode_status == src_data.power_management_response[0].status
    assert power_management_status.timestamp == src_data.power_management_response[1]

    # sample_base_unit_status = sample_base_unit_status.as_timezone(datetime.timezone.utc)

    # statuses = db_session.query(BaseUnitStatusModel).all()
    # assert len(statuses) == 1
    assert db_session.query(BaseUnitStatusModel).count() == 1
    status = db_session.query(BaseUnitStatusModel).filter_by(base_unit_id=base_unit.id).first()
    assert status is not None

    # sample_status_timestamp = sample_status_timestamp.astimezone(datetime.timezone.utc)
    assert status.base_unit_id == base_unit.id
    assert status.current_uptime == int(src_data.base_unit_status[0].current_uptime.total_seconds())
    assert status.total_uptime == int(src_data.base_unit_status[0].total_uptime.total_seconds())
    assert status.error_code == src_data.base_unit_status[0].error_code
    assert status.error_message == src_data.base_unit_status[0].error_message
    assert status.first_used == src_data.base_unit_status[0].first_used
    assert status.timestamp == src_data.base_unit_status[1]


    assert db_session.query(BaseUnitUsageStatusModel).count() == 1
    usage_status = db_session.query(BaseUnitUsageStatusModel).filter_by(base_unit_id=base_unit.id).first()
    assert usage_status is not None
    assert usage_status.base_unit_id == base_unit.id
    assert usage_status.in_use == src_data.base_unit_usage_status[0].in_use
    assert usage_status.sharing == src_data.base_unit_usage_status[0].sharing
    assert usage_status.timestamp == src_data.base_unit_usage_status[1]


    readings = db_session.query(SensorReadingModel).all()
    assert len(readings) == len(src_data.temperature_history.readings)
    for reading_data in src_data.temperature_history.readings:
        # reading_data = reading_data.as_timezone(tzinfo)
        reading_model = db_session.query(SensorReadingModel).filter_by(
            timestamp=reading_data.timestamp,
            sensor_type=reading_data.sensor,
            base_unit_id=base_unit.id,
        ).first()
        assert reading_model is not None
        assert reading_model.value == reading_data.value
        assert reading_model.to_data() == reading_data

    temp_history = base_unit.to_temperature_history_data(db_session)
    assert temp_history.readings == src_data.temperature_history.readings
