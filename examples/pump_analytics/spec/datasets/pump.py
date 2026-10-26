"""Pump-level observation scope and declarative dataframe transformations."""

from examples.pump_analytics.functions import analytics
from examples.pump_analytics.spec import entity

from uptimely.spec.python import Dataset, Feature, FunctionMapping, RowScope, ref


class Pump(Dataset):
    """One observation per pump, derived from timestamped telemetry."""

    id = "pump_dataset"
    description = "One row per pump with collapsed condition information."
    entity = entity.PUMP
    row_scope = RowScope(
        grain="One row per pump",
        filtering="Telemetry available to the source dataset",
    )

    bearing_temperature_by_pump = FunctionMapping(
        function=analytics.maximum,
        arguments=dict(  # noqa: C408
            dataset=ref.dataset("pump_telemetry_dataset").dataframe,
            feature=ref.feature("bearing_temperature"),
            dimensions=[ref.dimension(key.id).id for key in entity.dimensions],
            output=ref.feature("bearing_temperature_max").id,
        ),
        outputs=[
            Feature(
                name="bearing_temperature_max",
                type="float",
                unit="C",
                description="Maximum observed bearing temperature",
            )
        ],
    )

    health_signal_normalized = FunctionMapping(
        function=analytics.normalize_health_signal,
        arguments=dict(  # noqa: C408
            dataset=ref.current_dataset().dataframe,
            scale_feature=ref.feature("bearing_temperature_max"),
            lower_bound=-1.0,
            upper_bound=1.0,
            scaling_features=[ref.feature("bearing_temperature_max")],
            output=ref.feature("health_signal_normalized").id,
        ),
        outputs=[
            Feature(
                name="health_signal_normalized",
                type="float",
                description="Normalized bearing-temperature health signal by pump.",
            )
        ],
    )
