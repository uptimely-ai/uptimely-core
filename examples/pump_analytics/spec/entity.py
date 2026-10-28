"""Entity declarations for the pump analytics project."""

from uptimely import Entity

from . import dimension

PUMP_TELEMETRY = Entity(
    id="pump_telemetry",
    name="Pump telemetry",
    description=(
        "A one-minute pump record identified by plant, production line, pump, and timestamp"
    ),
    dimensions=[
        dimension.PLANT,
        dimension.PRODUCTION_LINE,
        dimension.PUMP,
        dimension.TIMESTAMP,
    ],
)

PUMP = Entity(
    id="pump",
    name="Pump",
    description="Pump-level information collapsed from timestamped telemetry",
    dimensions=[dimension.PLANT, dimension.PRODUCTION_LINE, dimension.PUMP],
)

entities = [PUMP_TELEMETRY, PUMP]
