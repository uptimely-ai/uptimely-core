"""Combined Python specification for example 1."""

from examples.example_1.spec.datasets import pump, telemetry

from uptimely.spec.python_spec import dimension, entity

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

# Runtime resource values for `?storage.<id>.<attribute>` references,
# supplied to the engine, not the spec.
storage_resources = {
    "pump_reference_source": {"path": "examples/example_1/data/pump_reference.json"},
    "telemetry_source": {"path": "examples/example_1/data/pump_telemetry.json"},
    "telemetry_archive_source": {"path": "examples/example_1/data/pump_telemetry_archive.json"},
}

entities = [
    entity.Entity(
        id="pump_telemetry",
        name="Pump telemetry",
        description=(
            "A one-minute pump record identified by plant, production line, pump, and timestamp"
        ),
        dimensions=["plant", "production_line", "pump", "timestamp"],
        datasets=[telemetry.telemetry_dataset],
    ),
    entity.Entity(
        id="pump",
        name="Pump",
        description="Pump-level information collapsed from timestamped telemetry",
        dimensions=["plant", "production_line", "pump"],
        datasets=[pump.pump_dataset],
    ),
]
