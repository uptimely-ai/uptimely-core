"""Pump-level dataset declarations for the pump analytics project."""

from uptimely.spec.python_spec import bind, dataset, feature, mapping, ref

from . import functions

pump_features = [
    feature.Feature(id="plant", type="string", description="Manufacturing plant identifier"),
    feature.Feature(id="production_line", type="string", description="Production line identifier"),
    feature.Feature(id="pump", type="string", description="Centrifugal pump asset identifier"),
    feature.Feature(
        id="bearing_temperature_max",
        type="float",
        unit="C",
        description="Maximum observed bearing temperature",
    ),
    feature.Feature(
        id="health_signal_normalized",
        type="float",
        description="Normalized bearing-temperature health signal by pump.",
    ),
]

pump_mappings = [
    mapping.Collapse(
        id="bearing_temperature_by_pump",
        bind=bind.bind(
            ref.function(functions.calculation.maximum),
            feature=ref.feature("bearing_temperature"),
            dataset=ref.dataset("pump_telemetry_dataset").dataframe,
            dimensions=[ref.dimension(name).id for name in ("plant", "production_line", "pump")],
            output=ref.feature("bearing_temperature_max").id,
        ),
        inputs=[ref.feature("bearing_temperature")],
        outputs=[
            ref.feature("plant"),
            ref.feature("production_line"),
            ref.feature("pump"),
            ref.feature("bearing_temperature_max"),
        ],
    ),
    mapping.Vectorize(
        id="health_signal_normalized",
        bind=bind.bind(
            ref.function(functions.calculation.normalize_health_signal),
            scale_feature=ref.feature("bearing_temperature_max"),
            lower_bound=-1.0,
            upper_bound=1.0,
            scaling_features=[ref.feature("bearing_temperature_max")],
            dataset=ref.current_dataset().dataframe,
            output=ref.feature("health_signal_normalized").id,
        ),
        inputs=[ref.feature("bearing_temperature_max")],
        outputs=[ref.feature("health_signal_normalized")],
    ),
]

PUMP_DATASET = dataset.Dataset(
    id="pump_dataset",
    description="One row per pump with collapsed condition information.",
    row_scope=dataset.RowScope(
        grain="One row per pump",
        filtering="Telemetry available to the source dataset",
    ),
    features=pump_features,
    mappings=pump_mappings,
)
