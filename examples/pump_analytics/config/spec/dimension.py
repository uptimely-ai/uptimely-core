"""Dimension declarations for the pump analytics specification."""

from uptimely.spec.python_spec import dimension

dimensions = [
    dimension.Dimension(id="plant", type="string", description="Manufacturing plant identifier"),
    dimension.Dimension(
        id="production_line",
        type="string",
        description="Production line identifier",
        parent="plant",
    ),
    dimension.Dimension(
        id="pump",
        type="string",
        description="Centrifugal pump asset identifier",
        parent="production_line",
    ),
    dimension.Dimension(
        id="timestamp",
        type="datetime",
        description="UTC timestamp of pump telemetry at one-minute grain",
    ),
]
