"""Python source with a relative import within an installed package."""

from uptimely.spec.python import (
    Binding,
    Dimension,
    Feature,
    Operator,
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
    grain = [row.resolution("row")]

    assembly = [
        Operator(
            id="read",
            outputs=[Feature(id="value")],
            compute=Binding(
                ref.function(functions.Readers.values),
            ),
        )
    ]


python_spec = Spec(profiles=[Values], name="Installed analytics")
