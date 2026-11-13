"""Project-wide physical constants profile."""

from example.src import io

from uptimely import Binding, Feature, FeatureSet, Interface, Operator, Profile, merge, ref


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

    assembly = [
        Operator(
            id="read_constants",
            interface=Interface(
                outputs=[features.gravity, features.room_temperature],
            ),
            compute=Binding(
                function=io.read_file,
                arguments=dict(
                    source=ref.params("constants_source"),
                    schema={"gravity": "float", "room_temperature": "float"},
                    rename={
                        "gravity": features.gravity,
                        "room_temperature": features.room_temperature,
                    },
                ),
            ),
            merge=merge.default(),
        )
    ]
