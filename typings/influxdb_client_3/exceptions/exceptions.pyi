from _typeshed import Incomplete
from dataclasses import dataclass
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

@dataclass(frozen=True)
class InfluxDBPartialWriteLineError:
    line_number: int
    error_message: str
    original_line: str

class InfluxDBPartialWriteError(InfluxDBError):
    line_errors: Incomplete
    def __init__(self, response: HTTPResponse, line_errors: list[InfluxDBPartialWriteLineError]) -> None: ...
    @classmethod
    def from_response(cls, response: HTTPResponse): ...
