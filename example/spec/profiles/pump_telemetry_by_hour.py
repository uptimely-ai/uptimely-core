"""Cooling-pump telemetry by hour profile declaration."""

from example.spec import dimension
from example.src import analytics

from uptimely import Binding, Feature, FeatureSet, Interface, Operator, Profile, merge, ref


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
    name = "Cooling Pump Telemetry by Hour"
    description = "Maximum motor-bearing temperature per cooling pump and hour."
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
                ),
            ),
            merge=merge.default(),
        )
    ]
