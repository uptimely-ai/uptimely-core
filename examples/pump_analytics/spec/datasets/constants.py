"""Project-wide physical constants."""

from examples.pump_analytics.functions import analytics

from uptimely import Action, Feature, Profile, ref


class Constants(Profile):
    """One row containing project-wide physical constants."""

    id = "constants_dataset"
    name = "Project Constants"
    description = "Physical constants used by pump analytics."
    category = "configuration"
    producers = [
        Action(
            id="read_constants",
            function=analytics.read_constants,
            arguments={"source": ref.source("constants_source")},
            outputs=[
                Feature(
                    id="gravity",
                    type="float",
                    unit="m/s^2",
                    description="Gravitational acceleration used in pump analytics.",
                ),
                Feature(
                    id="room_temperature",
                    type="float",
                    unit="C",
                    description="Ambient room temperature used as the thermal reference.",
                ),
            ],
        )
    ]
