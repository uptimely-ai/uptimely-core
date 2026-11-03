"""Python source with a relative import within an installed package."""

from uptimely.spec.python import (
    Action,
    Dimension,
    Feature,
    Grain,
    Profile,
    Resolution,
    Spec,
    ref,
)

from . import functions

row = Dimension(
    id="row",
    resolutions=[Resolution(id="row", key="row", type="integer")],
)


class Values(Profile):
    id = "values"
    grain = [Grain(row, "row")]

    producers = [
        Action(
            id="read",
            function=ref.function(functions.Readers.values, kind="read"),
            arguments={},
            outputs=[Feature(id="value")],
        )
    ]


python_spec = Spec(profiles=[Values], name="Installed analytics")
