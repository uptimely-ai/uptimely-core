"""Cooling-pump telemetry by hour profile declaration."""

import pump_analytics as analytics
import pump_io as io
from spec import dimension

from uptimely import Bind, Feature, FeatureSet, Operator, Profile, ref


class PumpTelemetryByHourFeatures(FeatureSet):
    """Features declared by the hour-level profile."""

    bearing_temperature_max = Feature(
        id="bearing_temperature_hour_max",
        type="float",
        unit="C",
        description="Maximum observed motor-bearing temperature at this profile's grain.",
    )


class PumpTelemetryByHour(Profile):
    """Maximum motor-bearing temperature at cooling-pump-and-hour grain."""

    id = "pump_telemetry_by_hour"
    name = "Telemetry by Hour"
    description = "Maximum motor-bearing temperature per cooling pump and hour."
    category = "Telemetry"
    grain = [
        dimension.MACHINE_DIMENSION.at("machine"),
        dimension.MACHINE_TIMESTAMP.at("hour"),
    ]
    features = PumpTelemetryByHourFeatures()
    seed = "aggregate_telemetry"
    assembly = [
        Operator(
            id="aggregate_telemetry",
            inputs=[ref.input("bearing_temperature")],
            compute=Bind(
                analytics.aggregate,
                dataset=ref.dataset("pump_telemetry"),
                aggregations={"bearing_temperature": "max"},
                dimensions=[
                    ref.key("pump_id"),
                    ref.key("hour"),
                ],
                rename={"bearing_temperature": ref.output("bearing_temperature_hour_max")},
            ),
        ),
        Operator(
            id="write_hourly_telemetry",
            compute=Bind(
                io.write_file,
                dataset=ref.dataset(),
                features=[ref.input("bearing_temperature_hour_max")],
                output=ref.paths("pump_telemetry_by_hour_output"),
            ),
        ),
    ]
