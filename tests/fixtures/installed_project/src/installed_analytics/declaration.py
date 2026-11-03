"""Python source with a relative import within an installed package."""

from uptimely.spec.python import (
    Action,
    Dimension,
    Entity,
    Feature,
    Profile,
    Spec,
    ref,
)

from . import functions

row = Dimension(id="row", type="integer")
sample = Entity(
    id="sample",
    name="Sample",
    dimensions=[row],
)


class Values(Profile):
    id = "values"
    entity = sample

    producers = [
        Action(
            id="read",
            function=ref.function(functions.Readers.values, kind="read"),
            arguments={},
            outputs=[Feature(id="value")],
        )
    ]


python_spec = Spec(
    dimensions=[row], entities=[sample], name="Installed analytics", datasets=[Values]
)
