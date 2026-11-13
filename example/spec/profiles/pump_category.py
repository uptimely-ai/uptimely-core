"""Cooling-pump category profile declaration."""

from example.spec import dimension
from example.src import analytics, io

from uptimely import Binding, Feature, FeatureSet, Interface, Operator, Profile, merge, ref


class PumpCategoryFeatures(FeatureSet):
    """Features declared by the cooling-pump category profile."""

    bearing_temperature_max = Feature(
        id="bearing_temperature_category_max",
        type="float",
        unit="C",
        description="Maximum observed motor-bearing temperature at this profile's grain.",
    )
    max_capacity = Feature(
        id="max_capacity_category",
        type="float",
        unit="m3/h",
        description="Default maximum chilled-water flow capacity for the pump category.",
    )


class PumpCategory(Profile):
    """Maximum motor-bearing temperature by cooling-pump category."""

    id = "pump_category"
    name = "Cooling Pump Category"
    description = "Maximum motor-bearing temperature for each cooling-pump category."
    category = "Cooling System"
    grain = [dimension.MACHINE_DIMENSION.resolution("machine_category")]
    scope = "Cooling-pump categories declared in the data-center asset registry"
    features = PumpCategoryFeatures()
    assembly = [
        Operator(
            id="read_pump_category",
            interface=Interface(outputs=[features.max_capacity]),
            compute=Binding(
                function=io.read_file,
                arguments=dict(
                    source=ref.params("pump_category_source"),
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
                    dimensions=[dimension.MACHINE_DIMENSION.resolution("machine_category").key],
                    output=features.bearing_temperature_max,
                ),
            ),
            merge=merge.default(),
        ),
    ]
