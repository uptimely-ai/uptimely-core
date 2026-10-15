"""Entity declarations for the pump analytics specification."""

from uptimely.analytics.python import entity

from . import dataset_pump, dataset_telemetry, dimension

PUMP_TELEMETRY = entity.Entity(
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
    datasets=[dataset_telemetry.TELEMETRY_DATASET],
)

PUMP = entity.Entity(
    id="pump",
    name="Pump",
    description="Pump-level information collapsed from timestamped telemetry",
    dimensions=[dimension.PLANT, dimension.PRODUCTION_LINE, dimension.PUMP],
    datasets=[dataset_pump.PUMP_DATASET],
)

entities: list[entity.Entity] = [
    value for value in globals().copy().values() if isinstance(value, entity.Entity)
]
by_id: dict[str, entity.Entity] = {item.id: item for item in entities}
