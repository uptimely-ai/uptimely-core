"""Pump telemetry by hour profile declaration."""

from examples.pump_analytics.functions import analytics
from examples.pump_analytics.spec import dimension

from uptimely import Binding, Feature, FeatureSet, Interface, Operator, Profile, default_merge, ref


class PumpTelemetryByHourFeatures(FeatureSet):
    """Features declared by the hour-level profile."""

    bearing_temperature_max = Feature(
        id="bearing_temperature_hour_max",
        type="float",
        unit="C",
        description="Maximum observed bearing temperature at this profile's grain.",
    )


class PumpTelemetryByHour(Profile):
    """Maximum bearing temperature at pump-and-hour grain."""

    id = "pump_telemetry_by_hour"
    name = "Pump Telemetry by Hour"
    description = "Maximum bearing temperature per pump and hour."
    category = "Telemetry"
    grain = [
        dimension.MACHINE_DIMENSION.resolution("machine"),
        dimension.MACHINE_TIMESTAMP.resolution("hour"),
    ]
    features = PumpTelemetryByHourFeatures()
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
                        dimension.MACHINE_TIMESTAMP.resolution("hour").key,
                    ],
                    output=features.bearing_temperature_max,
                    filter_column="",
                    filter_value="",
                ),
            ),
            merge=default_merge(),
        )
    ]
