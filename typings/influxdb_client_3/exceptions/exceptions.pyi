from _typeshed import Incomplete
from urllib3 import HTTPResponse as HTTPResponse

logger: Incomplete

class InfluxDB3ClientError(Exception): ...

class InfluxDB3ClientQueryError(InfluxDB3ClientError):
    message: Incomplete
    def __init__(self, error_message, *args, **kwargs) -> None: ...

class InfluxDBError(InfluxDB3ClientError):
    response: Incomplete
    message: Incomplete
    retry_after: Incomplete
    def __init__(self, response: HTTPResponse = None, message: str = None) -> None: ...
    def getheaders(self): ...
