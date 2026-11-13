"""Cooling-pump telemetry by day profile declaration."""

from example.spec import dimension
from example.src import analytics, io

from uptimely import Binding, Feature, FeatureSet, Interface, Operator, Profile, merge, ref


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
    name = "Cooling Pump Telemetry by Day"
    description = "Maximum motor-bearing temperature per cooling pump and day."
    category = "Telemetry"
    grain = [
        dimension.MACHINE_DIMENSION.resolution("machine"),
        dimension.MACHINE_TIMESTAMP.resolution("day"),
    ]
    features = PumpTelemetryByDayFeatures()
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
                        dimension.MACHINE_TIMESTAMP.resolution("day").key,
                    ],
                    output=features.bearing_temperature_max,
                ),
            ),
            merge=merge.default(),
        ),
        Operator(
            id="write_pump_telemetry_by_day",
            interface=Interface(outputs=[]),
            compute=Binding(
                function=io.write_file,
                arguments=dict(
                    dataset=ref.dataset(),
                    features=[features.bearing_temperature_max],
                    output=ref.paths("pump_telemetry_by_day_output"),
                ),
            ),
        ),
    ]
