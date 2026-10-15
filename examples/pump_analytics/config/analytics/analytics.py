"""Combined pump analytics Python declarations."""

from uptimely.analytics import python as analytics_python

from . import dimension, entity

dimensions = dimension.dimensions
entities = entity.entities

python_analytics = analytics_python.PythonAnalytics(
    entities=entities,
    dimensions=dimensions,
    name="Pump analytics",
)
