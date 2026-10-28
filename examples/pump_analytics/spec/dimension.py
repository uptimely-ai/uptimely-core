"""Dimension declarations for the pump analytics project."""

from uptimely import Dimension

PLANT = Dimension(
    id="plant",
    type="string",
    description="Manufacturing plant identifier",
)

PRODUCTION_LINE = Dimension(
    id="production_line",
    type="string",
    description="Production line identifier",
    parent=PLANT.id,
)

PUMP = Dimension(
    id="pump",
    type="string",
    description="Centrifugal pump asset identifier",
    parent=PRODUCTION_LINE.id,
)

TIMESTAMP = Dimension(
    id="timestamp",
    type="datetime",
    description="UTC timestamp of pump telemetry at one-minute grain",
)
