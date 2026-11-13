"""Dimension declarations for the data-center cooling pump project."""

from uptimely import Dimension, Resolution

MACHINE_DIMENSION = Dimension(
    id="machine_dimension",
    description="Cooling system pump",
    resolutions=[
        Resolution(id="machine", key="pump_id", type="string", parent="machine_series"),
        Resolution(
            id="machine_series",
            key="machine_series_id",
            type="string",
            parent="machine_category",
        ),
        Resolution(id="machine_category", key="machine_category_id", type="string"),
    ],
)

FACILITY_DIMENSION = Dimension(
    id="facility_dimension",
    description="Server room and its parent data center",
    resolutions=[
        Resolution(id="server_room", key="server_room_id", type="string", parent="data_center"),
        Resolution(id="data_center", key="data_center_id", type="string"),
    ],
)

MACHINE_TIMESTAMP = Dimension(
    id="machine_timestamp",
    description="UTC timestamp of cooling pump telemetry at one-minute grain",
    resolutions=[
        Resolution(id="timestamp", key="timestamp", type="datetime", parent="minute"),
        Resolution(id="minute", key="minute", type="datetime", parent="hour"),
        Resolution(id="hour", key="hour", type="datetime", parent="day"),
        Resolution(id="day", key="day", type="datetime"),
    ],
)
