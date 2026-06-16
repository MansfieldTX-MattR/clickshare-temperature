from __future__ import annotations
from typing import TYPE_CHECKING
from pathlib import Path

from clickshare_temperature.log_archive import LogEntry, LogArchive
from clickshare_temperature.temperature_history import (
    SensorReading,
    TemperatureHistory,
)
from clickshare_temperature.types import BaseUnitInfo

if TYPE_CHECKING:
    from .log_data_helpers import LogEntryTestCase



def test_log_entry_parsing(log_entry_test_case: LogEntryTestCase) -> None:
    line, expected = log_entry_test_case
    assert LogEntry.from_log_line(line) == expected


def test_log_archive_parsing(
    log_archive_file: Path,
    log_archive_expected_files: list[Path],
    log_entry_test_cases: list[LogEntryTestCase],
) -> None:
    archive = LogArchive()
    archive.parse_archive_file(log_archive_file)
    extracted_files = [f.filename for f in archive.log_files]

    assert set(extracted_files) == set(log_archive_expected_files)
    assert len(archive.log_files) == len(log_archive_expected_files)

    parsed_entries = list(archive.all_entries(unique=True))

    assert len(parsed_entries) == len(log_entry_test_cases)
    for parsed_entry, expected_case in zip(parsed_entries, log_entry_test_cases):
        assert parsed_entry == expected_case.expected


def test_temperature_history_from_log_archive(
    sample_base_unit_info: BaseUnitInfo,
    log_archive_file: Path,
    log_entry_sensor_readings: list[SensorReading],
) -> None:
    archive_bytes = log_archive_file.read_bytes()
    temperature_history = TemperatureHistory.from_archive_bytes(sample_base_unit_info, archive_bytes)

    expected_readings = log_entry_sensor_readings
    assert len(temperature_history.readings) == len(expected_readings)
    for reading, expected in zip(temperature_history.readings, expected_readings):
        assert reading == expected


def test_temperature_history_from_log_archive_file(
    log_archive_file: Path,
    log_entry_sensor_readings: list[SensorReading],
) -> None:
    temperature_history = TemperatureHistory.from_archive_file(log_archive_file)

    expected_readings = log_entry_sensor_readings
    assert len(temperature_history.readings) == len(expected_readings)
    for reading, expected in zip(temperature_history.readings, expected_readings):
        assert reading == expected
