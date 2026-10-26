"""Python source with a relative import within an installed package."""

from uptimely.spec.python import (
    Dataset,
    Dimension,
    Entity,
    Feature,
    FunctionMapping,
    PythonSpec,
    ref,
)

from . import functions

sample = Entity(
    id="sample",
    name="Sample",
    dimensions=[Dimension(id="row", type="integer")],
)


class Values(Dataset):
    id = "values"
    entity = sample

    read = FunctionMapping(
        function=ref.function(functions.Readers.values, operation="read"),
        arguments={},
        outputs=[Feature(name="value")],
    )


python_spec = PythonSpec(name="Installed analytics", datasets=[Values])
