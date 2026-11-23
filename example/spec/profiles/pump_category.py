"""Cooling-pump category profile declaration."""

import pump_analytics as analytics
import pump_io as io
from spec import dimension

from uptimely import Bind, Feature, FeatureSet, Operator, Profile, merge, ref


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
    seed = "read_pump_category"
    assembly = [
        Operator(
            id="read_pump_category",
            outputs=[features.max_capacity],
            compute=Bind(
                io.read_file,
                source=ref.paths("pump_category_source"),
                rename={"max_capacity": ref.output("max_capacity_category")},
                schema={"max_capacity": "float"},
            ),
        ),
        Operator(
            inputs=[ref.input("bearing_temperature")],
            compute=Bind(
                analytics.aggregate,
                dataset=ref.dataset("pump_telemetry"),
                aggregations={"bearing_temperature": "max"},
                dimensions=[ref.key("machine_category_id")],
                rename={"bearing_temperature": ref.output("bearing_temperature_category_max")},
            ),
            merge=merge.default(),
        ),
        Operator(
            compute=Bind(
                io.write_file,
                dataset=ref.dataset(),
                features=[
                    ref.input("bearing_temperature_category_max"),
                    ref.input("max_capacity_category"),
                ],
                output=ref.paths("pump_category_output"),
            ),
        ),
    ]
