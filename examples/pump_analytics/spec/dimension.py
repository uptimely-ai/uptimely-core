"""Dimension declarations for the pump analytics project."""

from uptimely import Dimension, Resolution

MACHINE = Dimension(
    id="machine",
    description="Centrifugal machine and its parent production groupings",
    resolutions=[
        Resolution(id="machine", key="pump_id", type="string", parent="production_line"),
        Resolution(id="production_line", key="production_line_id", type="string", parent="plant"),
        Resolution(id="plant", key="plant_id", type="string"),
    ],
)

TIMESTAMP = Dimension(
    id="timestamp",
    description="UTC timestamp of pump telemetry at one-minute grain",
    resolutions=[
        Resolution(id="timestamp", key="timestamp", type="datetime"),
    ],
)
