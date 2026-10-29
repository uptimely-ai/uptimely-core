"""Pump-level observation scope and declarative dataframe transformations."""

from examples.pump_analytics.functions import analytics
from examples.pump_analytics.spec import entity

from uptimely import Action, Dataset, Feature, RowScope, ref


class Pump(Dataset):
    """One observation per pump, derived from timestamped telemetry."""

    id = "pump_dataset"
    description = "One row per pump with collapsed condition information."
    entity = entity.PUMP
    row_scope = RowScope(
        grain="One row per pump",
        filtering="Telemetry available to the source dataset",
    )

    producers = [
        Action(
            id="bearing_temperature_by_pump",
            function=analytics.aggregate,
            arguments=dict(  # noqa: C408
                dataset=ref.dataframe("pump_telemetry_dataset"),
                feature=ref.column("bearing_temperature"),
                method="max",
                dimensions=[ref.dimension(key.id).id for key in entity.dimensions],
                output=ref.output("bearing_temperature_max"),
            ),
            outputs=[
                Feature(
                    name="bearing_temperature_max",
                    type="float",
                    unit="C",
                    description="Maximum observed bearing temperature",
                )
            ],
        ),
        Action(
            id="health_signal_normalized",
            function=analytics.min_max_scale,
            arguments=dict(  # noqa: C408
                dataset=ref.dataframe(),
                feature=ref.column("bearing_temperature_max"),
                lower_bound=-1.0,
                upper_bound=1.0,
                features=[ref.column("bearing_temperature_max")],
                output=ref.output("health_signal_normalized"),
            ),
            outputs=[
                Feature(
                    name="health_signal_normalized",
                    type="float",
                    description="Normalized bearing-temperature health signal by pump.",
                )
            ],
        ),
    ]
