from _typeshed import Incomplete
from influxdb_client_3.write_client.client.write.point import DEFAULT_WRITE_PRECISION as DEFAULT_WRITE_PRECISION, ordered_tag_keys as ordered_tag_keys
from influxdb_client_3.write_client.domain import WritePrecision as WritePrecision

logger: Incomplete

class DataframeSerializer:
    data_frame: Incomplete
    f: Incomplete
    field_indexes: Incomplete
    first_field_maybe_null: Incomplete
    chunk_size: Incomplete
    def __init__(self, data_frame, point_settings, precision=..., chunk_size: int = None, **kwargs) -> None: ...
    def serialize(self, chunk_idx: int = None): ...
    def number_of_chunks(self): ...

def data_frame_to_list_of_points(data_frame, point_settings, precision=..., **kwargs): ...
