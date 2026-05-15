from __future__ import annotations
from typing import NamedTuple
from pathlib import Path
import datetime

import pytest

from clickshare_temperature.log_archive import LogEntry, LogArchive


class LogEntryTestCase(NamedTuple):
    line: str
    expected: LogEntry


LOG_ENTRY_TEST_CASES: list[LogEntryTestCase] = [
    LogEntryTestCase(
        "2026-04-28T14:58:42.993182+00:00 ClickShare-1234567890 : [INFO] DHCP: ===== eth0 RENEW: START - IP ROUTE:  =====",
        LogEntry(
            timestamp=datetime.datetime.fromisoformat(
                "2026-04-28T14:58:42.993182+00:00"
            ),
            hostname="ClickShare-1234567890",
            process="",
            level="INFO",
            message="DHCP: ===== eth0 RENEW: START - IP ROUTE:  =====",
            process_number=None,
        ),
    ),
    LogEntryTestCase(
        "2026-05-12T16:05:00.283536-05:00 ClickShare-1234567890 rsyslogd: [origin software=\"rsyslogd\" swVersion=\"8.2312.0\" x-pid=\"2973\" x-info=\"https://www.rsyslog.com\"] rsyslogd was HUPed",
        LogEntry(
            timestamp=datetime.datetime.fromisoformat(
                "2026-05-12T16:05:00.283536-05:00"
            ),
            hostname="ClickShare-1234567890",
            process="rsyslogd",
            level=None,
            message="[origin software=\"rsyslogd\" swVersion=\"8.2312.0\" x-pid=\"2973\" x-info=\"https://www.rsyslog.com\"] rsyslogd was HUPed",
            process_number=None,
        ),
    ),
    LogEntryTestCase(
        "2026-05-12T16:06:00.260163-05:00 ClickShare-1234567890 crond[1322]: wakeup dt=50",
        LogEntry(
            timestamp=datetime.datetime.fromisoformat(
                "2026-05-12T16:06:00.260163-05:00"
            ),
            hostname="ClickShare-1234567890",
            process="crond",
            level=None,
            message="wakeup dt=50",
            process_number=1322,
        ),
    ),
    LogEntryTestCase(
        "2026-05-12T16:06:00.293588-05:00 ClickShare-1234567890 kernel: EXT4-fs (dm-3): re-mounted. Opts: nodelalloc,data=journal. Quota mode: disabled.",
        LogEntry(
            timestamp=datetime.datetime.fromisoformat(
                "2026-05-12T16:06:00.293588-05:00"
            ),
            hostname="ClickShare-1234567890",
            process="kernel",
            level=None,
            message="EXT4-fs (dm-3): re-mounted. Opts: nodelalloc,data=journal. Quota mode: disabled.",
            process_number=None,
        ),
    ),
    LogEntryTestCase(
        "2026-05-12T16:06:27.434937-05:00 ClickShare-1234567890 NetworkManager: [INFO] [7f16c75976c0] Temperature of wlan0: 49",
        LogEntry(
            timestamp=datetime.datetime.fromisoformat(
                "2026-05-12T16:06:27.434937-05:00"
            ),
            hostname="ClickShare-1234567890",
            process="NetworkManager",
            level="INFO",
            message="[7f16c75976c0] Temperature of wlan0: 49",
            process_number=None,
        ),
    ),
    LogEntryTestCase(
        "2026-05-12T16:07:41.427914-05:00 ClickShare-1234567890 CentralStore: [INFO] [7f5a5e531f40] Sensor readout CPUFanSpeed = 2814 RPM",
        LogEntry(
            timestamp=datetime.datetime.fromisoformat(
                "2026-05-12T16:07:41.427914-05:00"
            ),
            hostname="ClickShare-1234567890",
            process="CentralStore",
            level="INFO",
            message="[7f5a5e531f40] Sensor readout CPUFanSpeed = 2814 RPM",
            process_number=None,
        ),
    ),
    LogEntryTestCase(
        "2026-05-12T16:07:41.427927-05:00 ClickShare-1234567890 CentralStore: [INFO] [7f5a5e531f40] Sensor readout CPUTemperature = 38.8 C",
        LogEntry(
            timestamp=datetime.datetime.fromisoformat(
                "2026-05-12T16:07:41.427927-05:00"
            ),
            hostname="ClickShare-1234567890",
            process="CentralStore",
            level="INFO",
            message="[7f5a5e531f40] Sensor readout CPUTemperature = 38.8 C",
            process_number=None,
        ),
    ),
    LogEntryTestCase(
        "2026-04-28T10:09:20.876497-05:00 ClickShare-1234567890 kernel:",
        LogEntry(
            timestamp=datetime.datetime.fromisoformat(
                "2026-04-28T10:09:20.876497-05:00"
            ),
            hostname="ClickShare-1234567890",
            process="kernel",
            level=None,
            message="",
            process_number=None,
        ),
    ),
    LogEntryTestCase(
        "2026-04-28T10:09:21.876497-05:00 ClickShare-1234567890 kernel:   ",
        LogEntry(
            timestamp=datetime.datetime.fromisoformat(
                "2026-04-28T10:09:21.876497-05:00"
            ),
            hostname="ClickShare-1234567890",
            process="kernel",
            level=None,
            message="",
            process_number=None,
        ),
    ),
    LogEntryTestCase(
        "2026-04-28T14:58:42.993182+00:00 ClickShare-1234567890 : DHCP: ===== eth0 RENEW: START - IP ROUTE:  =====",
        LogEntry(
            timestamp=datetime.datetime.fromisoformat(
                "2026-04-28T14:58:42.993182+00:00"
            ),
            hostname="ClickShare-1234567890",
            process="",
            level=None,
            message="DHCP: ===== eth0 RENEW: START - IP ROUTE:  =====",
            process_number=None,
        ),
    ),
]

@pytest.fixture(params=LOG_ENTRY_TEST_CASES)
def log_entry_test_case(request: pytest.FixtureRequest) -> LogEntryTestCase:
    return request.param


def test_log_entry_parsing(log_entry_test_case) -> None:
    line, expected = log_entry_test_case
    assert LogEntry.from_log_line(line) == expected
