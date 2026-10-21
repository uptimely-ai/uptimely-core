"""Dimension declarations for the pump analytics project."""

from uptimely.spec.python import dimension

PLANT = dimension.Dimension(
    id="plant",
    type="string",
    description="Manufacturing plant identifier",
)

PRODUCTION_LINE = dimension.Dimension(
    id="production_line",
    type="string",
    description="Production line identifier",
    parent=PLANT.id,
)

PUMP = dimension.Dimension(
    id="pump",
    type="string",
    description="Centrifugal pump asset identifier",
    parent=PRODUCTION_LINE.id,
)

TIMESTAMP = dimension.Dimension(
    id="timestamp",
    type="datetime",
    description="UTC timestamp of pump telemetry at one-minute grain",
)

dimensions: list[dimension.Dimension] = [
    value for value in globals().copy().values() if isinstance(value, dimension.Dimension)
]
by_id: dict[str, dimension.Dimension] = {item.id: item for item in dimensions}
