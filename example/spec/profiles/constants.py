"""Project-wide physical constants profile."""

import pump_io as io

from uptimely import Bind, Feature, FeatureSet, Operator, Profile, ref


class ConstantsFeatures(FeatureSet):
    """Features declared by the constants profile."""

    gravity = Feature(
        id="gravity",
        type="float",
        unit="m/s^2",
        description="Gravitational acceleration for engineering calculations.",
    )
    room_temperature = Feature(
        id="room_temperature",
        type="float",
        unit="C",
        description="Ambient pump-room temperature used as the thermal reference.",
    )


class Constants(Profile):
    """One row containing project-wide physical constants."""

    id = "constants"
    name = "Project Constants"
    description = "Physical constants used by cooling pump analytics."
    category = "Configuration"
    features = ConstantsFeatures()
    seed = "read_constants"

    assembly = [
        Operator(
            id="read_constants",
            outputs=[features.gravity, features.room_temperature],
            compute=Bind(
                io.read_file,
                source=ref.paths("constants_source"),
                schema={"gravity": "float", "room_temperature": "float"},
                rename={
                    "gravity": features.gravity,
                    "room_temperature": features.room_temperature,
                },
            ),
        ),
        Operator(
            outputs=[],
            compute=Bind(
                io.write_file,
                dataset=ref.dataset(),
                features=[features.gravity, features.room_temperature],
                output=ref.paths("constants_output"),
            ),
        ),
    ]
