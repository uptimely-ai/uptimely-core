"""Spec assembly for simple analytics."""

from uptimely.spec.python import PythonSpec

from . import entity
from .datasets.simple_analytics import SimpleAnalytics

dataset_ = SimpleAnalytics()

python_spec = PythonSpec(
    datasets={entity.SIMPLE_ANALYTICS: [dataset_]},
    name="Simple analytics",
)
