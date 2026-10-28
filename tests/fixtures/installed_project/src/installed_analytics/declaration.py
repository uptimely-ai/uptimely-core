"""Python source with a relative import within an installed package."""

from uptimely.spec.python import (
    Action,
    Dataset,
    Dimension,
    Entity,
    Feature,
    PythonSpec,
    ref,
)

from . import functions

row = Dimension(id="row", type="integer")
sample = Entity(
    id="sample",
    name="Sample",
    dimensions=[row],
)


class Values(Dataset):
    id = "values"
    entity = sample

    producers = [
        Action(
            id="read",
            function=ref.function(functions.Readers.values, kind="read"),
            arguments={},
            outputs=[Feature(name="value")],
        )
    ]


python_spec = PythonSpec(
    dimensions=[row], entities=[sample], name="Installed analytics", datasets=[Values]
)
