"""Cooling-pump series profile declaration."""

import pump_analytics as analytics
import pump_io as io
from spec import dimension

from uptimely import Bind, Feature, FeatureSet, Operator, Profile, merge, ref


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
    grain = [dimension.MACHINE_DIMENSION.at("machine_series")]
    scope = "Cooling-pump series declared in the data-center asset registry"
    features = PumpSeriesFeatures()
    seed = "read_pump_series"
    assembly = [
        Operator(
            id="read_pump_series",
            outputs=[features.max_capacity],
            compute=Bind(
                io.read_file,
                source=ref.paths("pump_series_source"),
                rename={"max_capacity": ref.output("max_capacity_series")},
                schema={"max_capacity": "float"},
            ),
        ),
        Operator(
            inputs=[ref.input("bearing_temperature")],
            compute=Bind(
                analytics.aggregate,
                dataset=ref.dataset("pump_telemetry"),
                aggregations={"bearing_temperature": "max"},
                dimensions=[ref.key("machine_series_id")],
                rename={"bearing_temperature": ref.output("bearing_temperature_series_max")},
            ),
            merge=merge.default(),
        ),
        Operator(
            compute=Bind(
                io.write_file,
                dataset=ref.dataset(),
                features=[
                    ref.input("bearing_temperature_series_max"),
                    ref.input("max_capacity_series"),
                ],
                output=ref.paths("pump_series_output"),
            ),
        ),
    ]
