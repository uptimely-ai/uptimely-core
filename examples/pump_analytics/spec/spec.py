"""Combined spec declarations for the pump analytics project."""

from uptimely.spec import python as spec_python

from . import dimension, entity

dimensions = dimension.dimensions
entities = entity.entities

python_spec = spec_python.PythonSpec(
    entities=entities,
    dimensions=dimensions,
    name="Pump analytics",
)
