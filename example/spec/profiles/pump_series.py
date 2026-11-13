"""Cooling-pump series profile declaration."""

from example.spec import dimension
from example.src import analytics, io

from uptimely import Binding, Feature, FeatureSet, Interface, Operator, Profile, merge, ref


class PumpSeriesFeatures(FeatureSet):
    """Features declared by the cooling-pump series profile."""

    bearing_temperature_max = Feature(
        id="bearing_temperature_series_max",
        type="float",
        unit="C",
        description="Maximum observed motor-bearing temperature at this profile's grain.",
    )
    max_capacity = Feature(
        id="max_capacity_series",
        type="float",
        unit="m3/h",
        description="Default maximum chilled-water flow capacity for the pump series.",
    )


class PumpSeries(Profile):
    """Maximum motor-bearing temperature by cooling-pump series."""

    id = "pump_series"
    name = "Cooling Pump Series"
    description = "Maximum motor-bearing temperature for each cooling-pump series."
    category = "Cooling System"
    grain = [dimension.MACHINE_DIMENSION.resolution("machine_series")]
    scope = "Cooling-pump series declared in the data-center asset registry"
    features = PumpSeriesFeatures()
    assembly = [
        Operator(
            id="read_pump_series",
            interface=Interface(outputs=[features.max_capacity]),
            compute=Binding(
                function=io.read_file,
                arguments=dict(
                    source=ref.params("pump_series_source"),
                    rename={"max_capacity": features.max_capacity},
                    schema={"max_capacity": "float"},
                ),
            ),
            merge=merge.default(),
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
                ),
            ),
            merge=merge.default(),
        ),
    ]
