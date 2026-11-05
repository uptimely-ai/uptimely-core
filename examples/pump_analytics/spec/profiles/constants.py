"""Project-wide physical constants profile."""

from examples.pump_analytics.functions import analytics

from uptimely import Action, Feature, FeatureSet, Profile, ref


class ConstantsFeatures(FeatureSet):
    """Features declared by the constants profile."""

    gravity = Feature(
        id="gravity",
        type="float",
        unit="m/s^2",
        description="Gravitational acceleration used in pump analytics.",
    )
    room_temperature = Feature(
        id="room_temperature",
        type="float",
        unit="C",
        description="Ambient room temperature used as the thermal reference.",
    )


class Constants(Profile):
    """One row containing project-wide physical constants."""

    id = "constants"
    name = "Project Constants"
    description = "Physical constants used by pump analytics."
    category = "Configuration"
    features = ConstantsFeatures()

    actions = [
        Action(
            id="read_constants",
            function=analytics.read_constants,
            arguments={"source": ref.source("constants_source")},
            outputs=[features.gravity, features.room_temperature],
        )
    ]
