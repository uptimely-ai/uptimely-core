"""Combined pump analytics Python specification."""

from uptimely.spec import python_spec

from . import dimension, entity

dimensions = dimension.dimensions
entities = entity.entities

python_specification = python_spec.PythonSpecification(
    entities=entities,
    dimensions=dimensions,
    name="Pump analytics",
)
