"""Pump-level dataset declarations for example 1."""

from uptimely.spec.python_spec import bind, dataset, feature, fragment, ref

from ...functions import calculation

pump_collapse = fragment.Collapse(
    id="bearing_temperature_by_pump",
    bind=bind.bind(
        calculation.aggregate_by_dimension,
        dataset=ref.dataset("pump_telemetry_dataset"),
        dimensions=[
            ref.dimension("plant"),
            ref.dimension("production_line"),
            ref.dimension("pump"),
        ],
        aggregations={
            "bearing_temperature_max": feature.aggregation(
                calculation.maximum,
                feature=ref.feature("bearing_temperature"),
            )
        },
    ),
    features=[
        feature.Raw(id="plant", type="string", description="Manufacturing plant identifier"),
        feature.Raw(id="production_line", type="string", description="Production line identifier"),
        feature.Raw(id="pump", type="string", description="Centrifugal pump asset identifier"),
        feature.Raw(
            id="bearing_temperature_max",
            type="float",
            unit="C",
            description="Maximum observed bearing temperature",
        ),
    ],
)

pump_dataset = dataset.Dataset(
    id="pump_dataset",
    description="One row per pump with collapsed condition information.",
    row_scope=dataset.RowScope(
        grain="One row per pump",
        filtering="Telemetry available to the source dataset",
    ),
    collapse=[pump_collapse],
    vectorize=[
        feature.Vectorize(
            id="health_signal_normalized",
            description="Normalized bearing-temperature health signal by pump.",
            bind=bind.bind(
                calculation.normalize_health_signal,
                scale_feature=ref.feature("bearing_temperature_max"),
                lower_bound=-1.0,
                upper_bound=1.0,
                scaling_features=[ref.feature("bearing_temperature_max")],
            ),
        )
    ],
)
