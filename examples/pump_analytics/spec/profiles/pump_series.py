"""Pump-series profile declaration."""

from examples.pump_analytics.functions import analytics, source
from examples.pump_analytics.spec import dimension

from uptimely import Binding, Feature, FeatureSet, Interface, Operator, Profile, default_merge, ref


class PumpSeriesFeatures(FeatureSet):
    """Features declared by the pump-series profile."""

    bearing_temperature_max = Feature(
        id="bearing_temperature_series_max",
        type="float",
        unit="C",
        description="Maximum observed bearing temperature at this profile's grain.",
    )
    max_capacity = Feature(
        id="max_capacity_series",
        type="float",
        unit="m3/h",
        description="Default maximum flow capacity for the pump series.",
    )


class PumpSeries(Profile):
    """Maximum bearing temperature by pump series."""

    id = "pump_series"
    name = "Pump Series"
    description = "Maximum bearing temperature for each pump series."
    category = "Machines"
    grain = [dimension.MACHINE_DIMENSION.resolution("machine_series")]
    scope = "Pump series declared in the asset registry"
    features = PumpSeriesFeatures()
    assembly = [
        Operator(
            id="read_pump_series",
            interface=Interface(outputs=[features.max_capacity]),
            compute=Binding(
                function=source.read_file,
                arguments=dict(
                    source=ref.params("pump_series_source"),
                    rename={"max_capacity": features.max_capacity},
                    schema={"max_capacity": "float"},
                ),
            ),
            merge=default_merge(),
        ),
        Operator(
            id="bearing_temperature_max",
            interface=Interface(
                inputs=[ref.feature("bearing_temperature")],
                outputs=[features.bearing_temperature_max],
            ),
            compute=Binding(
                function=analytics.aggregate,
                arguments=dict(
                    dataset=ref.dataset("pump_telemetry"),
                    feature=ref.feature("bearing_temperature"),
                    method="max",
                    dimensions=[dimension.MACHINE_DIMENSION.resolution("machine_series").key],
                    output=features.bearing_temperature_max,
                    filter_column="",
                    filter_value="",
                ),
            ),
            merge=default_merge(),
        ),
    ]
