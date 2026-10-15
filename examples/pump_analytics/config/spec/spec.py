"""Combined pump analytics Python specification."""

from uptimely.analytics import python as python_spec

from . import dimension, entity

dimensions = dimension.dimensions
entities = entity.entities

python_specification = python_spec.PythonAnalytics(
    entities=entities,
    dimensions=dimensions,
    name="Pump analytics",
)
