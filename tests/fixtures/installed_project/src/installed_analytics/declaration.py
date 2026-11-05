"""Python source with a relative import within an installed package."""

from uptimely.spec.python import (
    Binding,
    Dimension,
    Feature,
    Grain,
    Interface,
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
    grain = [Grain(row, "row")]

    assembly = [
        Operator(
            id="read",
            interface=Interface(outputs=[Feature(id="value")]),
            compute=Binding(function=ref.function(functions.Readers.values, kind="read")),
        )
    ]


python_spec = Spec(profiles=[Values], name="Installed analytics")
