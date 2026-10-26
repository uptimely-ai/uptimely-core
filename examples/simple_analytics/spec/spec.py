"""Spec assembly for simple analytics."""

from uptimely.spec.python import PythonSpec

from .datasets.simple_analytics import SimpleAnalytics

python_spec = PythonSpec(
    datasets=[SimpleAnalytics],
    name="Simple analytics",
)
