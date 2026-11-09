"""Pump telemetry by minute profile declaration."""

from examples.pump_analytics.functions import analytics
from examples.pump_analytics.spec import dimension

from uptimely import Binding, Feature, FeatureSet, Interface, Operator, Profile, default_merge, ref


class PumpTelemetryByMinuteFeatures(FeatureSet):
    """Features declared by the minute-level profile."""

    bearing_temperature_max = Feature(
        id="bearing_temperature_minute_max",
        type="float",
        unit="C",
        description="Maximum observed bearing temperature at this profile's grain.",
    )


class PumpTelemetryByMinute(Profile):
    """Maximum bearing temperature at pump-and-minute grain."""

    id = "pump_telemetry_by_minute"
    name = "Pump Telemetry by Minute"
    description = "Maximum bearing temperature per pump and minute."
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
                    filter_column="",
                    filter_value="",
                ),
            ),
            merge=default_merge(),
        )
    ]
