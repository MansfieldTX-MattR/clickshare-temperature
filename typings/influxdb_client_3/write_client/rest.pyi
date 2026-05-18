from _typeshed import Incomplete
from influxdb_client_3.exceptions import InfluxDBError as InfluxDBError
from influxdb_client_3.write_client.configuration import Configuration as Configuration

class ApiException(InfluxDBError):
    status: Incomplete
    reason: Incomplete
    body: Incomplete
    headers: Incomplete
    def __init__(self, status=None, reason=None, http_resp=None) -> None: ...

class _BaseRESTClient:
    logger: Incomplete
    @staticmethod
    def log_request(method: str, url: str): ...
    @staticmethod
    def log_response(status: str): ...
    @staticmethod
    def log_body(body: object, prefix: str): ...
    @staticmethod
    def log_headers(headers: dict[str, str], prefix: str): ...
