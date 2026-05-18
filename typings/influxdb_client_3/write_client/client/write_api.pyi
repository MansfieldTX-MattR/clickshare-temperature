import types
from _typeshed import Incomplete
from dataclasses import dataclass
from enum import Enum
from influxdb_client_3.write_client.client._base import _BaseWriteApi
from influxdb_client_3.write_client.client.util.helpers import get_org_query_param as get_org_query_param
from influxdb_client_3.write_client.client.write.dataframe_serializer import DataframeSerializer as DataframeSerializer
from influxdb_client_3.write_client.client.write.point import DEFAULT_WRITE_PRECISION as DEFAULT_WRITE_PRECISION, Point as Point, sanitize_tag_order as sanitize_tag_order
from influxdb_client_3.write_client.client.write.retry import WritesRetry as WritesRetry
from influxdb_client_3.write_client.domain import WritePrecision as WritePrecision
from reactivex import Observable
from typing import Any, Iterable, NamedTuple

DEFAULT_WRITE_NO_SYNC: bool
DEFAULT_WRITE_TIMEOUT: int
SERIALIZER_KWARGS: Incomplete
logger: Incomplete

class WriteType(Enum):
    batching = 1
    asynchronous = 2
    synchronous = 3

class DefaultWriteOptions(Enum):
    write_type = ...
    write_precision = DEFAULT_WRITE_PRECISION
    no_sync = DEFAULT_WRITE_NO_SYNC
    timeout = DEFAULT_WRITE_TIMEOUT

class WriteOptions:
    write_type: Incomplete
    batch_size: Incomplete
    flush_interval: Incomplete
    jitter_interval: Incomplete
    retry_interval: Incomplete
    max_retries: Incomplete
    max_retry_delay: Incomplete
    max_retry_time: Incomplete
    exponential_base: Incomplete
    write_scheduler: Incomplete
    max_close_wait: Incomplete
    write_precision: Incomplete
    timeout: Incomplete
    no_sync: Incomplete
    tag_order: Incomplete
    def __init__(self, write_type: WriteType = ..., batch_size: int = 1000, flush_interval: int = 1000, jitter_interval: int = 0, retry_interval: int = 5000, max_retries: int = 5, max_retry_delay: int = 125000, max_retry_time: int = 180000, exponential_base: int = 2, max_close_wait: int = 300000, write_precision=..., no_sync=..., tag_order=None, timeout=..., write_scheduler=...) -> None: ...
    def to_retry_strategy(self, **kwargs): ...

SYNCHRONOUS: Incomplete
ASYNCHRONOUS: Incomplete

class PointSettings:
    defaultTags: Incomplete
    def __init__(self, **default_tags) -> None: ...
    def add_default_tag(self, key, value) -> None: ...

class _BatchItemKey:
    bucket: Incomplete
    org: Incomplete
    precision: Incomplete
    kwargs: Incomplete
    def __init__(self, bucket, org, precision=..., **kwargs) -> None: ...
    def __hash__(self) -> int: ...
    def __eq__(self, o: object) -> bool: ...

class _BatchItem:
    key: Incomplete
    data: Incomplete
    size: Incomplete
    def __init__(self, key: _BatchItemKey, data, size: int = 1) -> None: ...
    def to_key_tuple(self) -> tuple[str, str, str]: ...

class _BatchResponse:
    data: Incomplete
    exception: Incomplete
    def __init__(self, data: _BatchItem, exception: Exception = None) -> None: ...

class WriteApi(_BaseWriteApi):
    def __init__(self, influxdb_client, write_options: WriteOptions = ..., point_settings: PointSettings = ..., **kwargs) -> None: ...
    def write(self, bucket: str, org: str = None, record: str | Iterable['str'] | Point | Iterable['Point'] | dict | Iterable['dict'] | bytes | Iterable['bytes'] | Observable | NamedTuple | Iterable['NamedTuple'] | dataclass | Iterable['dataclass'] = None, write_precision: WritePrecision = None, **kwargs) -> Any: ...
    def flush(self) -> None: ...
    def close(self) -> None: ...
    def __enter__(self): ...
    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: types.TracebackType | None) -> None: ...
    def __del__(self) -> None: ...
