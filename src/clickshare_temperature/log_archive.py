from __future__ import annotations
import io
from typing import Self, NamedTuple, TypedDict, NotRequired, Iterator, Unpack
from pathlib import Path
import tarfile
import gzip
import tempfile
from dataclasses import dataclass, field
import datetime
import re

from .baseunit_api import download_logs
from .types import AuthInfo, LogLevel, LogLevels, AioHttpRequestOptions, AioHttpSessionOptions


UTC = datetime.timezone.utc

LOG_LINE_PATTERN: re.Pattern[str] = re.compile(r"^(\S+) (\S+) (.*?):\s*(.*)$")
PROCESS_PATTERN: re.Pattern[str] = re.compile(r"^(\S+?)(?:\[(\d*)\])?$")
LEVEL_PREFIX_PATTERN: re.Pattern[str] = re.compile(r"^\[(\w+)\] (.+)$")

# ENTRY_DT_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"




class TmpDir:
    """Context manager for a temporary directory.

    The directory and its contents will be automatically deleted when the context is exited.
    """
    def __init__(self) -> None:
        self._tmpdir: tempfile.TemporaryDirectory|None = None
        self._tmppath: Path|None = None

    @property
    def path(self) -> Path:
        if self._tmppath is None:
            raise ValueError("Temporary directory has not been created yet.")
        return self._tmppath

    def open(self) -> Path:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmppath = Path(self._tmpdir.name).resolve()
        return self._tmppath

    def close(self) -> None:
        if self._tmpdir is not None:
            self._tmpdir.cleanup()
            self._tmpdir = None
            self._tmppath = None

    def __enter__(self) -> Path:
        return self.open()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class _LogFileSerializeTD(TypedDict):
    filename: str
    index: int
    entries: list[_LogEntrySerializeTD]


@dataclass
class LogFile:
    """A log file extracted from the log archive."""
    filename: Path
    index: int
    entries: list[LogEntry] = field(default_factory=list)
    entries_by_timestamp: dict[datetime.datetime, list[LogEntry]] = field(default_factory=dict)

    def parse_entries(self, filename: Path|None = None) -> None:
        """Parse the log file into a sequence of LogEntry objects."""
        if len(self.entries):
            raise ValueError("Log entries have already been parsed.")
        content_bytes = (filename or self.filename).read_bytes()
        content = content_bytes.decode("utf-8", errors="replace")
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            entry = LogEntry.from_log_line(line)
            self.entries.append(entry)
            entry_list = self.entries_by_timestamp.setdefault(entry.timestamp, [])
            entry_list.append(entry)

    def serialize(self) -> _LogFileSerializeTD:
        """Serialize the LogFile to a dictionary."""
        return {
            "filename": self.filename.name,
            "index": self.index,
            "entries": [entry.serialize() for entry in self.entries],
        }

    @classmethod
    def deserialize(cls, data: _LogFileSerializeTD) -> Self:
        """Deserialize a LogFile from a dictionary."""
        return cls(
            filename=Path(data["filename"]),
            index=data["index"],
            entries=[LogEntry.deserialize(entry_data) for entry_data in data["entries"]],
        )

    def serialize_str(self) -> str:
        """Serialize the LogFile to a string."""
        lines = []
        for entry in self.entries:
            lines.append(entry.serialize_str())
        return "\n".join(lines)

    @classmethod
    def deserialize_str(cls, log_str: str, filename: Path|None = None) -> Self:
        """Deserialize a LogFile from a string."""
        entries = []
        for line in log_str.splitlines():
            line = line.strip()
            if not line:
                continue
            entry = LogEntry.from_log_line(line)
            entries.append(entry)
        return cls(
            filename=filename or Path("info"),
            index=0,
            entries=entries,
        )

    def __iter__(self):
        if not self.entries:
            self.parse_entries()
        yield from self.values()

    def __len__(self):
        if not self.entries:
            self.parse_entries()
        return len(self.entries)

    def __contains__(self, entry: LogEntry) -> bool:
        if not self.entries:
            self.parse_entries()
        if entry.timestamp not in self.entries_by_timestamp:
            return False
        for e in self.entries_by_timestamp[entry.timestamp]:
            if e == entry:
                return True
        return False

    def keys(self) -> Iterator[datetime.datetime]:
        if not self.entries:
            self.parse_entries()
        yield from sorted(self.entries_by_timestamp.keys())

    def values(self) -> Iterator[LogEntry]:
        if not self.entries:
            self.parse_entries()
        for timestamp in self.keys():
            yield from self.entries_by_timestamp[timestamp]

    def items(self) -> Iterator[tuple[datetime.datetime, LogEntry]]:
        if not self.entries:
            self.parse_entries()
        for timestamp in self.keys():
            for entry in self.entries_by_timestamp[timestamp]:
                yield timestamp, entry


class _LogEntrySerializeTD(TypedDict):
    timestamp: str
    hostname: str
    process: str
    level: LogLevel|None
    message: str
    process_number: NotRequired[int|None]


class LogEntry(NamedTuple):
    """A log entry parsed from a log file."""
    timestamp: datetime.datetime
    hostname: str
    process: str
    level: LogLevel|None
    message: str
    process_number: int|None = None

    @classmethod
    def from_log_line(cls, line: str) -> Self:
        """Parse a log line into a LogEntry
        """
        def log_level_or_none(level_str: str) -> LogLevel|None:
            """Convert a log level string to a :type:`LogLevel` (a string literal type)
            or return None if the string is not a valid log level.
            """
            if level_str in LogLevels:
                return level_str
            return None

        match = LOG_LINE_PATTERN.match(line)
        if not match:
            raise ValueError(f"Invalid log line format: {line}")
        timestamp_str, hostname, process_part, message_part = match.groups()
        timestamp = datetime.datetime.fromisoformat(timestamp_str)
        process = process_part
        process_number_str = None
        if process_part:
            process_match = PROCESS_PATTERN.match(process_part)
            if not process_match:
                raise ValueError(f"Invalid process format in log line: {line}")
            process = process_match.group(1)
            process_number_str = process_match.group(2)
        process_number = int(process_number_str) if process_number_str else None
        level = None
        message = message_part
        level_match = LEVEL_PREFIX_PATTERN.match(message_part)
        if level_match:
            level_str, message = level_match.groups()
            level = log_level_or_none(level_str)
        return cls(
            timestamp=timestamp,
            hostname=hostname,
            process=process,
            level=level,
            message=message,
            process_number=process_number,
        )

    def serialize(self) -> _LogEntrySerializeTD:
        """Serialize the LogEntry to a dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "hostname": self.hostname,
            "process": self.process,
            "level": self.level,
            "message": self.message,
            "process_number": self.process_number,
        }

    @classmethod
    def deserialize(cls, data: _LogEntrySerializeTD) -> Self:
        """Deserialize a LogEntry from a dictionary."""
        timestamp = datetime.datetime.fromisoformat(data["timestamp"])
        return cls(
            timestamp=timestamp,
            hostname=data["hostname"],
            process=data["process"],
            level=data["level"],
            message=data["message"],
            process_number=data.get("process_number"),
        )

    def serialize_str(self) -> str:
        """Serialize the LogEntry to a log line string."""
        timestamp_str = self.timestamp.isoformat()
        level_str = f"[{self.level}] " if self.level is not None else ""
        process_str = (
            f"{self.process}[{self.process_number}]"
            if self.process_number is not None
            else self.process
        )
        return f"{timestamp_str} {self.hostname} {process_str}: {level_str}{self.message}"

    @classmethod
    def deserialize_str(cls, line: str) -> Self:
        """Deserialize a LogEntry from a log line string."""
        return cls.from_log_line(line)

    def __gt__(self, other: LogEntry|datetime.datetime) -> bool: # type: ignore[override]
        if isinstance(other, LogEntry):
            return self.timestamp > other.timestamp
        if isinstance(other, datetime.datetime):
            return self.timestamp > other
        return NotImplemented

    def __lt__(self, other: LogEntry|datetime.datetime) -> bool: # type: ignore[override]
        if isinstance(other, LogEntry):
            return self.timestamp < other.timestamp
        if isinstance(other, datetime.datetime):
            return self.timestamp < other
        return NotImplemented

    def __ge__(self, other: LogEntry|datetime.datetime) -> bool: # type: ignore[override]
        if isinstance(other, LogEntry):
            return self.timestamp >= other.timestamp
        if isinstance(other, datetime.datetime):
            return self.timestamp >= other
        return NotImplemented

    def __le__(self, other: LogEntry|datetime.datetime) -> bool: # type: ignore[override]
        if isinstance(other, LogEntry):
            return self.timestamp <= other.timestamp
        if isinstance(other, datetime.datetime):
            return self.timestamp <= other
        return NotImplemented


class _LogArchiveSerializeTD(TypedDict):
    log_files: list[_LogFileSerializeTD]


class LogArchive:
    """Context manager for a log archive.

    The log archive will be extracted to a temporary directory, which will be
    automatically deleted when the context is exited.

    The structure of the log archive is:

    - log/
      - info
      - info.1.gz
      - info.2.gz
      - ...

    """

    log_files: list[LogFile]

    def __init__(self) -> None:
        # self._archive_bytes = archive_bytes
        # self._tmpdir: TmpDir|None = None
        # self.log_files = []
        self.log_files = []

    @classmethod
    async def from_baseunit(
        cls,
        baseunit_ip: str,
        auth_info: AuthInfo|None = None,
        session_options: AioHttpSessionOptions|None = None,
        **request_options: Unpack[AioHttpRequestOptions],
    ) -> Self:
        """Create a LogArchive by downloading logs from the BaseUnit."""
        archive = cls()
        with TmpDir() as tmpdir:
            archive_path = tmpdir / "logs.tar.gz"
            with archive_path.open("wb") as f:
                await download_logs(
                    baseunit_ip,
                    chunk_handler=f.write,
                    auth_info=auth_info,
                    session_options=session_options,
                    **request_options
                )
            archive.parse_archive_file(archive_path)
        return archive

    def parse_archive_file(self, archive_path: Path) -> None:
        with TmpDir() as tmpdir:
            with tarfile.open(fileobj=gzip.GzipFile(fileobj=archive_path.open("rb"))) as tar:
                tar.extractall(path=tmpdir)
            self._parse_log_files(tmpdir)

    def parse_archive_bytes(self, archive_bytes: bytes) -> None:
        with TmpDir() as tmpdir:
            with tarfile.open(fileobj=gzip.GzipFile(fileobj=io.BytesIO(archive_bytes))) as tar:
                tar.extractall(path=tmpdir)
            self._parse_log_files(tmpdir)

    def _parse_log_files(self, tmpdir: Path) -> None:
        log_dir = tmpdir / "log"
        for p in log_dir.glob("info*"):
            if not p.is_file():
                continue
            suffixes = p.suffixes
            if len(suffixes) > 0:
                assert len(suffixes) == 2, f"Unexpected file in log archive: {p}"
                assert suffixes[-1] == ".gz", f"Unexpected file in log archive: {p}"
                index = int(suffixes[0].lstrip(".").lstrip("info"))
                is_gzipped = True
            else:
                index = 0
                is_gzipped = False

            relative_log_filename = Path("log") / p.name
            if is_gzipped:
                with gzip.open(p, "rb") as f:
                    log_content_bytes = f.read()
                    log_content = log_content_bytes.decode("utf-8")
                    log_filename = tmpdir / p.stem
                    log_filename.write_text(log_content)
            else:
                log_filename = p
            log_file = LogFile(filename=relative_log_filename, index=index)
            log_file.parse_entries(filename=log_filename)
            self.log_files.append(log_file)
        self.log_files.sort(key=lambda lf: lf.index)
        self.log_files.reverse()  # Logs are ordered from newest to oldest, so reverse the list to have oldest first

    def all_entries(self, unique: bool = True) -> Iterator[LogEntry]:
        """Get an iterator over all log entries in the archive, ordered by timestamp."""
        entries_seen: set[str] = set()
        for log_file in self.log_files:
            for entry in log_file.values():
                if unique and entry.serialize_str() in entries_seen:
                    continue
                entries_seen.add(entry.serialize_str())
                yield entry

    def combine_entries_with(self, other: LogArchive) -> LogArchive:
        """Combine the log entries from this archive with another archive, returning a new LogArchive.

        The combined archive will contain all unique log entries from both archives, ordered by timestamp.
        """
        combined_entries = list(self.all_entries(unique=True))
        other_entries = list(other.all_entries(unique=True))
        for entry in other_entries:
            if self.has_entry(entry):
                continue
            combined_entries.append(entry)
        combined_entries.sort(key=lambda e: e.timestamp)
        combined_archive = LogArchive()
        log_file = LogFile(filename=Path("info"), index=0, entries=combined_entries)
        combined_archive.log_files.append(log_file)
        return combined_archive

    def has_entry(self, entry: LogEntry) -> bool:
        """Check if the given log entry is present in the archive."""
        for log_file in self.log_files:
            if entry in log_file:
                return True
        return False

    def __iter__(self):
        return iter(self.log_files)

    def __len__(self):
        return len(self.log_files)

    def serialize(self) -> _LogArchiveSerializeTD:
        """Serialize the LogArchive to a dictionary."""
        return {
            "log_files": [log_file.serialize() for log_file in self.log_files]
        }

    @classmethod
    def deserialize(cls, data: _LogArchiveSerializeTD) -> Self:
        """Deserialize a LogArchive from a dictionary."""
        archive = cls()
        archive.log_files = [
            LogFile.deserialize(log_file_data) for log_file_data in data["log_files"]
        ]
        return archive

    def serialize_str(self) -> str:
        """Serialize the LogArchive to a string."""
        lines = []
        for entry in self.all_entries(unique=True):
            lines.append(entry.serialize_str())
        return "\n".join(lines)

    @classmethod
    def deserialize_str(cls, archive_str: str) -> Self:
        """Deserialize a LogArchive from a string."""
        archive = cls()
        # Only one log file is supported when deserializing from a string
        log_file = LogFile.deserialize_str(archive_str)
        archive.log_files.append(log_file)
        return archive

    def serialize_entries(self) -> list[_LogEntrySerializeTD]:
        """Serialize all log entries in the archive to a list of dictionaries."""
        return [entry.serialize() for entry in self.all_entries(unique=True)]

    @classmethod
    def deserialize_entries(cls, entries_data: list[_LogEntrySerializeTD]) -> Self:
        """Deserialize a LogArchive from a list of log entry dictionaries."""
        archive = cls()
        entries = [LogEntry.deserialize(entry_data) for entry_data in entries_data]
        entries.sort(key=lambda e: e.timestamp)
        log_file = LogFile(filename=Path("info"), index=0, entries=entries)
        archive.log_files.append(log_file)
        return archive
