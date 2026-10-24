"""Python source with a relative import within an installed package."""

from uptimely.spec import python as api
from uptimely.spec.python import dataset, dimension, entity, feature, mapping, ref

from . import functions

python_spec = api.PythonSpec(
    name="Installed analytics",
    datasets={
        entity.Entity(
            id="sample",
            name="Sample",
            dimensions=[dimension.Dimension(id="row", type="integer")],
        ): [
            dataset.Dataset(
                id="values",
                mappings={
                    "read": mapping.FunctionMapping(
                        function=ref.function(functions.Readers.values, operation="read"),
                        arguments={},
                        outputs=[feature.Feature(name="value")],
                    )
                },
            )
        ]
    },
)
