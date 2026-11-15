"""Cooling-pump category profile declaration."""

import pump_analytics as analytics
import pump_io as io
from spec import dimension

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
            interface=Interface(outputs=[features.max_capacity]),
            stage=Binding(
                io.read_file,
                source=ref.paths("pump_category_source"),
                rename={"max_capacity": features.max_capacity},
                schema={"max_capacity": "float"},
            ),
            merge=merge.default(),
        ),
        Operator(
            interface=Interface(
                inputs=[ref.feature("bearing_temperature")],
                outputs=[features.bearing_temperature_max],
            ),
            stage=Binding(
                analytics.aggregate,
                dataset=ref.dataset("pump_telemetry"),
                aggregations={"bearing_temperature": "max"},
                dimensions=[dimension.MACHINE_DIMENSION.resolution("machine_category").key],
                rename={"bearing_temperature": features.bearing_temperature_max},
            ),
            merge=merge.default(),
        ),
        Operator(
            interface=Interface(outputs=[]),
            compute=Binding(
                io.write_file,
                dataset=ref.dataset(),
                features=[features.bearing_temperature_max, features.max_capacity],
                output=ref.paths("pump_category_output"),
            ),
        ),
    ]
