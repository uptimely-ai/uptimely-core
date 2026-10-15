"""Entity declarations for the pump analytics specification."""

from uptimely.spec.python_spec import entity

from . import dataset_pump, dataset_telemetry

entities = [
    entity.Entity(
        id="pump_telemetry",
        name="Pump telemetry",
        description=(
            "A one-minute pump record identified by plant, production line, pump, and timestamp"
        ),
        dimensions=["plant", "production_line", "pump", "timestamp"],
        datasets=[dataset_telemetry.telemetry_dataset],
    ),
    entity.Entity(
        id="pump",
        name="Pump",
        description="Pump-level information collapsed from timestamped telemetry",
        dimensions=["plant", "production_line", "pump"],
        datasets=[dataset_pump.pump_dataset],
    ),
]
