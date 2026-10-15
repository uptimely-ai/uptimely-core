"""Python authoring declarations for analytics specifications."""

from . import feature
from . import mappings as mapping
from .analytics import PythonAnalytics

__all__ = ["PythonAnalytics", "feature", "mapping"]
