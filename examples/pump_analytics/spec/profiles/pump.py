"""Pump-level profile and declarative dataframe transformations."""

from examples.pump_analytics.functions import analytics
from examples.pump_analytics.spec import dimension

from uptimely import Action, Binding, Feature, FeatureSet, Grain, Interface, Profile, ref


class PumpFeatures(FeatureSet):
    """Features declared by the pump profile."""

    bearing_temperature_max = Feature(
        id="bearing_temperature_max",
        type="float",
        unit="C",
        description="Maximum observed bearing temperature",
    )
    health_signal_normalized = Feature(
        id="health_signal_normalized",
        type="float",
        description="Normalized bearing-temperature health signal by pump.",
    )


class Pump(Profile):
    """One observation per pump, derived from timestamped telemetry."""

    id = "pump_profile"
    name = "Pump Summary"
    description = "One row per pump with collapsed condition information."
    category = "Machines"
    grain = [Grain(dimension.MACHINE, "machine")]
    scope = "Telemetry available to the source profile"
    features = PumpFeatures()

    assembly = [
        Action(
            id="bearing_temperature_by_pump",
            interface=Interface(
                outputs=[features.bearing_temperature_max],
            ),
            compute=Binding(
                function=analytics.aggregate,
                arguments=dict(
                    dataset=ref.dataframe("pump_telemetry"),
                    feature=ref.column("bearing_temperature"),
                    method="max",
                    dimensions=ref.current_profile().grain.ids,
                    output=ref.output("bearing_temperature_max"),
                ),
            ),
        ),
        Action(
            id="health_signal_normalized",
            interface=Interface(
                outputs=[features.health_signal_normalized],
            ),
            compute=Binding(
                function=analytics.min_max_scale,
                arguments=dict(
                    dataset=ref.dataframe(),
                    feature=ref.column("bearing_temperature_max"),
                    lower_bound=-1.0,
                    upper_bound=1.0,
                    features=[ref.column("bearing_temperature_max")],
                    output=ref.output("health_signal_normalized"),
                ),
            ),
        ),
    ]
