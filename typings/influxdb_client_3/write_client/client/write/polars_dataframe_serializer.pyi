from _typeshed import Incomplete
from influxdb_client_3.write_client.client.write.point import DEFAULT_WRITE_PRECISION as DEFAULT_WRITE_PRECISION, ordered_tag_keys as ordered_tag_keys

logger: Incomplete

class PolarsDataframeSerializer:
    data_frame: Incomplete
    point_settings: Incomplete
    precision: Incomplete
    chunk_size: Incomplete
    measurement_name: Incomplete
    tag_columns: Incomplete
    tag_order: Incomplete
    timestamp_column: Incomplete
    timestamp_timezone: Incomplete
    column_indices: Incomplete
    number_of_chunks: Incomplete
    def __init__(self, data_frame, point_settings, precision=..., chunk_size: int = None, **kwargs) -> None: ...
    def escape_key(self, value): ...
    def escape_value(self, value): ...
    def to_line_protocol(self, row): ...
    def serialize(self, chunk_idx: int = None): ...

def polars_data_frame_to_list_of_points(data_frame, point_settings, precision=..., **kwargs): ...
