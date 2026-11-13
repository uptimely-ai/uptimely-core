"""Cooling-pump telemetry by minute profile declaration."""

from example.spec import dimension
from example.src import analytics, io

from uptimely import Binding, Feature, FeatureSet, Interface, Operator, Profile, merge, ref


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
    name = "Cooling Pump Telemetry by Minute"
    description = "Maximum motor-bearing temperature per cooling pump and minute."
    category = "Telemetry"
    grain = [
        dimension.MACHINE_DIMENSION.resolution("machine"),
        dimension.MACHINE_TIMESTAMP.resolution("minute"),
    ]
    features = PumpTelemetryByMinuteFeatures()
    assembly = [
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
                    dimensions=[
                        dimension.MACHINE_DIMENSION.resolution("machine").key,
                        dimension.MACHINE_TIMESTAMP.resolution("minute").key,
                    ],
                    output=features.bearing_temperature_max,
                ),
            ),
            merge=merge.default(),
        ),
        Operator(
            id="write_pump_telemetry_by_minute",
            interface=Interface(outputs=[]),
            compute=Binding(
                function=io.write_file,
                arguments=dict(
                    dataset=ref.dataset(),
                    features=[features.bearing_temperature_max],
                    output=ref.paths("pump_telemetry_by_minute_output"),
                ),
            ),
        ),
    ]
