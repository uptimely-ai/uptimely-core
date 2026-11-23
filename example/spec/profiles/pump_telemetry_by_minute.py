"""Cooling-pump telemetry by minute profile declaration."""

import pump_analytics as analytics
import pump_io as io
from spec import dimension

from uptimely import Bind, Feature, FeatureSet, Operator, Profile, ref


class PumpTelemetryByMinuteFeatures(FeatureSet):
    """Features declared by the minute-level profile."""

    bearing_temperature_max = Feature(
        id="bearing_temperature_minute_max",
        type="float",
        unit="C",
        description="Maximum observed motor-bearing temperature at this profile's grain.",
    )


class PumpTelemetryByMinute(Profile):
    """Maximum motor-bearing temperature at cooling-pump-and-minute grain."""

    id = "pump_telemetry_by_minute"
    name = "Telemetry by Minute"
    description = "Maximum motor-bearing temperature per cooling pump and minute."
    category = "Telemetry"
    grain = [
        dimension.MACHINE_DIMENSION.resolution("machine"),
        dimension.MACHINE_TIMESTAMP.resolution("minute"),
    ]
    features = PumpTelemetryByMinuteFeatures()
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
                    dimension.MACHINE_DIMENSION.resolution("machine").key,
                    dimension.MACHINE_TIMESTAMP.resolution("minute").key,
                ],
                rename={"bearing_temperature": ref.output("bearing_temperature_minute_max")},
            ),
        ),
        Operator(
            compute=Bind(
                io.write_file,
                dataset=ref.dataset(),
                features=[ref.input("bearing_temperature_minute_max")],
                output=ref.paths("pump_telemetry_by_minute_output"),
            ),
        ),
    ]
