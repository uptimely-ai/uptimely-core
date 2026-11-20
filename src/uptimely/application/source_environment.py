"""Backward-compatible name for the project Python import scope."""

from uptimely.project.python_imports import expose

project_source_path = expose

__all__ = ["project_source_path"]
