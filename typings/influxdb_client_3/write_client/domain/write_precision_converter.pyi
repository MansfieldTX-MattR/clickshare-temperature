from influxdb_client_3.write_client.domain import WritePrecision as WritePrecision

class WritePrecisionConverter:
    @staticmethod
    def to_v2_api_string(precision): ...
    @staticmethod
    def to_v3_api_string(precision): ...
