import types
from _typeshed import Incomplete
from dataclasses import dataclass
from enum import Enum
from influxdb_client_3.exceptions import InfluxDBPartialWriteError as InfluxDBPartialWriteError
from influxdb_client_3.write_client._sync.rest_client import RestClient as RestClient
from influxdb_client_3.write_client.client.write.dataframe_serializer import DataframeSerializer as DataframeSerializer
from influxdb_client_3.write_client.client.write.point import DEFAULT_WRITE_PRECISION as DEFAULT_WRITE_PRECISION, Point as Point, sanitize_tag_order as sanitize_tag_order
from influxdb_client_3.write_client.client.write.retry import WritesRetry as WritesRetry
from influxdb_client_3.write_client.domain import WritePrecision as WritePrecision
from influxdb_client_3.write_client.domain.write_precision_converter import WritePrecisionConverter as WritePrecisionConverter
from influxdb_client_3.write_client.write_exceptions import ApiException as ApiException
from reactivex import Observable
from typing import Any, Iterable, NamedTuple

DEFAULT_WRITE_NO_SYNC: bool
DEFAULT_WRITE_TIMEOUT: int
DEFAULT_WRITE_ACCEPT_PARTIAL: Incomplete
DEFAULT_WRITE_USE_V2_API: Incomplete
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
    accept_partial = DEFAULT_WRITE_ACCEPT_PARTIAL
    use_v2_api = DEFAULT_WRITE_USE_V2_API
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
    accept_partial: Incomplete
    use_v2_api: Incomplete
    tag_order: Incomplete
    def __init__(self, write_type: WriteType = ..., batch_size: int = 1000, flush_interval: int = 1000, jitter_interval: int = 0, retry_interval: int = 5000, max_retries: int = 5, max_retry_delay: int = 125000, max_retry_time: int = 180000, exponential_base: int = 2, max_close_wait: int = 300000, write_precision=..., no_sync=..., tag_order=None, accept_partial=..., use_v2_api=..., timeout=..., write_scheduler=...) -> None: ...
    def validate(self) -> None: ...
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
    no_sync: Incomplete
    accept_partial: Incomplete
    use_v2_api: Incomplete
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

class WriteApi:
    PRIMITIVE_TYPES: Incomplete
    rest_client: Incomplete
    bucket: Incomplete
    org: Incomplete
    enable_gzip: Incomplete
    gzip_threshold: Incomplete
    timeout: Incomplete
    pool_threads: Incomplete
    default_header: Incomplete
    def __init__(self, bucket: str, org: str, gzip_threshold=None, enable_gzip: bool = False, timeout=None, pool_threads=None, default_header=None, rest_client: RestClient = None, write_options=None, point_settings=None, **kwargs) -> None: ...
    @property
    def pool(self): ...
    def write(self, bucket=None, org=None, record: str | Iterable['str'] | Point | Iterable['Point'] | dict | Iterable['dict'] | bytes | Iterable['bytes'] | Observable | NamedTuple | Iterable['NamedTuple'] | dataclass | Iterable['dataclass'] = None, write_precision: WritePrecision = None, **kwargs) -> Any: ...
    async def post_write_async(self, org, bucket, body, **kwargs): ...
    def call_api(self, resource_path, method, query_params=None, header_params=None, body=None, async_req=None, _request_timeout=None, urlopen_kw=None): ...
    def flush(self) -> None: ...
    def close(self) -> None: ...
    def __enter__(self): ...
    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: types.TracebackType | None) -> None: ...
    def __del__(self) -> None: ...
