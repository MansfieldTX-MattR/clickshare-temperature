from __future__ import annotations
import pytest
from typing import Iterator, TYPE_CHECKING
import datetime
from pathlib import Path


if TYPE_CHECKING:
    from pytest_codspeed import BenchmarkFixture

from sqlalchemy.orm import Session


from clickshare_temperature.types import SensorType, BaseUnitInfo
from clickshare_temperature.temperature_history import (
    SensorReading as SensorReadingData
)
from clickshare_temperature.orm import (
    set_engine_uri,
    get_engine_uri,
    init_db,
    get_session,
)
from clickshare_temperature.orm import models
from clickshare_temperature.orm.serialization import (
    serialize_database,
    deserialize_database,
)


from .conftest import _reset_engine



def generate_sensor_readings(
    num_readings: int,
    *sensor_types: SensorType,
    start_time: datetime.datetime = datetime.datetime(2024, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc),
    interval: datetime.timedelta = datetime.timedelta(minutes=1),
) -> Iterator[SensorReadingData]:
    """Generate a series of sensor readings for a given base unit and sensor types.
    """
    for i in range(num_readings):
        timestamp = start_time + i * interval
        for sensor_type in sensor_types:
            value = 20.0 + i * 0.1
            yield SensorReadingData(
                sensor=sensor_type,
                value=value,
                timestamp=timestamp,
            )


def generate_base_unit_data(
    num_units: int,
) -> list[BaseUnitInfo]:
    """Generate a list of BaseUnitInfo objects for testing.
    """
    return [
        BaseUnitInfo(
            ip_address=f"192.168.1.{i+1}",
            hostname=f"base-unit-{i+1}",
            room_name=f"Room {i+1}",
        )
        for i in range(num_units)
    ]



@pytest.fixture
def base_unit_data() -> list[BaseUnitInfo]:
    """Fixture to generate a list of 5 BaseUnitInfo objects for testing.
    """
    return generate_base_unit_data(num_units=5)


@pytest.fixture
def sensor_readings(
    base_unit_data: list[BaseUnitInfo]
) -> dict[BaseUnitInfo, dict[SensorType, list[SensorReadingData]]]:
    """Fixture to generate a dictionary of sensor readings for each base unit and sensor type.

    For each base unit, 100 sensor readings will be generated for each of the
    following sensor types:

    - "CPU"
    - "WLAN0"
    - "WLAN1"
    - "CPU_FAN"

    This results in a total of 4 sensor types * 100 readings = 400 readings per
    base unit. With 5 base units, this results in a total of
    5 * 400 = 2000 sensor readings.
    """
    num_readings = 100
    readings = {}
    sensor_types: tuple[SensorType, ...] = ("CPU", "WLAN0", "WLAN1", "CPU_FAN")
    for base_unit in base_unit_data:
        sensor_data: dict[SensorType, list[SensorReadingData]] = {
            sensor_type: [] for sensor_type in sensor_types
        }
        for reading in generate_sensor_readings(
            num_readings,
            *sensor_types,
        ):
            sensor_data[reading.sensor].append(reading)
        readings[base_unit] = sensor_data
    return readings


@pytest.fixture
def populated_db_session(
    db_session: Session,
    sensor_readings: dict[BaseUnitInfo, dict[SensorType, list[SensorReadingData]]],
) -> Session:
    """Fixture to populate the database session with generated sensor readings and base unit data
    """
    for base_unit_info, readings in sensor_readings.items():
        base_unit = models.BaseUnit.from_info(base_unit_info)
        db_session.add(base_unit)
        db_session.flush()  # Ensure base_unit gets an ID before adding readings
        for sensor_type, sensor_readings_list in readings.items():
            for reading in sensor_readings_list:
                reading_model = models.SensorReading.from_data(
                    base_unit=base_unit,
                    reading=reading,
                    session=db_session,
                )
                db_session.add(reading_model)
    db_session.commit()
    return db_session


def teardown_and_create_new_db_session(
    db_session: Session,
    tmp_path: Path,
    exist_ok: bool = False,
) -> Session:
    """Close the current session, reset the engine, create a new database file,
    and return a new session connected to it.
    """
    db_session.close()
    _reset_engine()

    db_file = tmp_path / "new.db"
    if db_file.exists():
        if exist_ok:
            db_file.unlink()
        else:
            raise FileExistsError(f"Database file already exists: {db_file}")
    new_uri = f"sqlite:///{db_file}"
    set_engine_uri(new_uri)
    assert str(get_engine_uri()) == str(new_uri)
    init_db()
    assert db_file.exists()
    new_db_session = get_session()

    assert new_db_session is not db_session
    assert new_db_session.query(models.BaseUnit).count() == 0
    assert new_db_session.query(models.SensorReading).count() == 0
    return new_db_session


def teardown_and_check_deserialization(
    db_session: Session,
    expected_data: dict[BaseUnitInfo, dict[SensorType, list[SensorReadingData]]],
    tmp_path: Path,
    json_str: str,
    exist_ok: bool = False,
) -> None:
    """Tear down and create a new database session, deserialize and verify
    the new database contents.
    """
    new_db_session = teardown_and_create_new_db_session(
        db_session,
        tmp_path,
        exist_ok=exist_ok,
    )

    deserialize_database(new_db_session, json_str)
    check_deserialized_database(new_db_session, expected_data)



def check_deserialized_database(
    session: Session,
    expected_data: dict[BaseUnitInfo, dict[SensorType, list[SensorReadingData]]],
) -> None:
    """Check that the deserialized database contains the expected data.
    """
    for base_unit_info, expected_readings in expected_data.items():
        base_unit = session.query(models.BaseUnit).filter_by(
            ip_address=base_unit_info.ip_address,
            hostname=base_unit_info.hostname,
            room_name=base_unit_info.room_name,
        ).one_or_none()
        assert base_unit is not None
        for sensor_type, expected_sensor_readings in expected_readings.items():
            sensor_readings = session.query(models.SensorReading).filter_by(
                base_unit_id=base_unit.id,
                sensor_type=sensor_type,
            ).order_by(models.SensorReading.timestamp).all()
            assert len(sensor_readings) == len(expected_sensor_readings)
            for reading, expected in zip(sensor_readings, expected_sensor_readings):
                assert reading.sensor_type == expected.sensor
                assert reading.value == expected.value
                assert reading.timestamp == expected.timestamp


@pytest.mark.benchmark(group="serialization")
def test_orm_serialization(
    benchmark: BenchmarkFixture,
    tmp_path: Path,
    populated_db_session: Session,
    sensor_readings: dict[BaseUnitInfo, dict[SensorType, list[SensorReadingData]]],
) -> None:
    """Benchmark the serialization of the database to a JSON string
    """
    def target() -> str:
        return serialize_database(populated_db_session)

    json_str = benchmark(target)

    teardown_and_check_deserialization(
        db_session=populated_db_session,
        expected_data=sensor_readings,
        tmp_path=tmp_path,
        json_str=json_str,
    )


@pytest.mark.benchmark(group="serialization")
def test_orm_deserialization(
    benchmark: BenchmarkFixture,
    tmp_path: Path,
    populated_db_session: Session,
    sensor_readings: dict[BaseUnitInfo, dict[SensorType, list[SensorReadingData]]],
) -> None:
    """Benchmark the deserialization of a JSON string into the database.

    Since a new database session must be used for each benchmark iteration,
    `benchmark.pedantic` must be used for the setup function.
    """
    json_str = serialize_database(populated_db_session)
    current_db_session = populated_db_session

    def setup() -> None:
        """Tear down the current database session and create a new one before
        each benchmark iteration
        """
        nonlocal current_db_session
        current_db_session = teardown_and_create_new_db_session(
            populated_db_session,
            tmp_path,
            exist_ok=True,
        )

    def target() -> None:
        deserialize_database(current_db_session, json_str)

    benchmark.pedantic(
        target,
        setup=setup,
        rounds=5,
        iterations=1,
    )

    check_deserialized_database(current_db_session, sensor_readings)



@pytest.mark.benchmark(group="serialization")
def test_orm_deserialization_already_populated(
    benchmark: BenchmarkFixture,
    populated_db_session: Session,
    sensor_readings: dict[BaseUnitInfo, dict[SensorType, list[SensorReadingData]]],
) -> None:
    """Benchmark the deserialization of a JSON string into a database that already
    contains data, which should result in all deserialized objects being detected as existing and
    no new objects being created.
    """
    json_str = serialize_database(populated_db_session)

    def target() -> None:
        deserialize_database(populated_db_session, json_str)

    benchmark(target)

    check_deserialized_database(populated_db_session, sensor_readings)
