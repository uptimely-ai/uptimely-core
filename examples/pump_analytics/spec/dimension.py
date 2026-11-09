"""Dimension declarations for the pump analytics project."""

from uptimely import Dimension, Resolution

MACHINE_DIMENSION = Dimension(
    id="machine_dimension",
    description="Centrifugal machine",
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
    description="Production line and its parent plant",
    resolutions=[
        Resolution(id="production_line", key="production_line_id", type="string", parent="plant"),
        Resolution(id="plant", key="plant_id", type="string"),
    ],
)

MACHINE_TIMESTAMP = Dimension(
    id="machine_timestamp",
    description="UTC timestamp of pump telemetry at one-minute grain",
    resolutions=[
        Resolution(id="timestamp", key="timestamp", type="datetime", parent="hour"),
        Resolution(id="minute", key="minute", type="datetime", parent="hour"),
        Resolution(id="hour", key="hour", type="datetime", parent="day"),
        Resolution(id="day", key="day", type="datetime"),
    ],
)
