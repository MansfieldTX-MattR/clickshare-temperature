from _typeshed import Incomplete
from influxdb_client_3.write_client.client.write.dataframe_serializer import DataframeSerializer as DataframeSerializer
from influxdb_client_3.write_client.configuration import Configuration as Configuration
from influxdb_client_3.write_client.service.write_service import WriteService as WriteService

LOGGERS_NAMES: Incomplete

class _BaseClient:
    url: Incomplete
    org: Incomplete
    default_tags: Incomplete
    conf: Incomplete
    auth_header_name: Incomplete
    auth_header_value: Incomplete
    retries: Incomplete
    profilers: Incomplete
    def __init__(self, url, token, debug=None, timeout: int = 10000, enable_gzip: bool = False, org: str = None, default_tags: dict = None, http_client_logger: str = None, **kwargs) -> None: ...

class _BaseWriteApi:
    def __init__(self, influxdb_client, point_settings=None) -> None: ...

class _Configuration(Configuration):
    enable_gzip: bool
    username: Incomplete
    password: Incomplete
    def __init__(self) -> None: ...
    def update_request_header_params(self, path: str, params: dict, should_gzip: bool = False): ...
    def update_request_body(self, path: str, body, should_gzip: bool = False): ...
