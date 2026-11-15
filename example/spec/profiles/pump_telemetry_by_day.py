"""Cooling-pump telemetry by day profile declaration."""

import pump_analytics as analytics
import pump_io as io
from spec import dimension

from uptimely import Bind, Feature, FeatureSet, Operator, Profile, ref


class PumpTelemetryByDayFeatures(FeatureSet):
    """Features declared by the day-level profile."""

    bearing_temperature_max = Feature(
        id="bearing_temperature_day_max",
        type="float",
        unit="C",
        description="Maximum observed motor-bearing temperature at this profile's grain.",
    )


class PumpTelemetryByDay(Profile):
    """Maximum motor-bearing temperature at cooling-pump-and-day grain."""

    id = "pump_telemetry_by_day"
    name = "Telemetry by Day"
    description = "Maximum motor-bearing temperature per cooling pump and day."
    category = "Telemetry"
    grain = [
        dimension.MACHINE_DIMENSION.resolution("machine"),
        dimension.MACHINE_TIMESTAMP.resolution("day"),
    ]
    features = PumpTelemetryByDayFeatures()
    seed = "aggregate_telemetry"
    assembly = [
        Operator(
            id="aggregate_telemetry",
            inputs=[ref.feature("bearing_temperature")],
            outputs=[features.bearing_temperature_max],
            seed=Bind(
                analytics.aggregate,
                dataset=ref.dataset("pump_telemetry"),
                aggregations={"bearing_temperature": "max"},
                dimensions=[
                    dimension.MACHINE_DIMENSION.resolution("machine").key,
                    dimension.MACHINE_TIMESTAMP.resolution("day").key,
                ],
                rename={"bearing_temperature": features.bearing_temperature_max},
            ),
        ),
        Operator(
            outputs=[],
            write=Bind(
                io.write_file,
                dataset=ref.dataset(),
                features=[features.bearing_temperature_max],
                output=ref.paths("pump_telemetry_by_day_output"),
            ),
        ),
    ]
