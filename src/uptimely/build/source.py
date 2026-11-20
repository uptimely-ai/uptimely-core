"""Compatibility aliases for project specification sources."""

from uptimely.project.spec_source import (
    JsonSourceInput,
    JsonSpecSource,
    PythonSpecSource,
    ResolvedSpecSource,
    SpecSourceResolver,
)

JsonSource = JsonSpecSource
PythonSource = PythonSpecSource
SpecSource = SpecSourceResolver

__all__ = [
    "JsonSource",
    "JsonSourceInput",
    "PythonSource",
    "ResolvedSpecSource",
    "SpecSource",
]
