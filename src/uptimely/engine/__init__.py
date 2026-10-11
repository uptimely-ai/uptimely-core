"""Execution engine and runtime adapters for portable plans."""

from .backend import (
    CallableLoader,
    DataFrameBackend,
    EntrypointLoader,
    PlanResourceResolver,
    PolarsBackend,
    ResourceResolver,
)
from .engine import Engine, EngineConfig
from .result import ExecutionResult

__all__ = [
    "Engine",
    "EngineConfig",
    "ExecutionResult",
    "DataFrameBackend",
    "ResourceResolver",
    "CallableLoader",
    "PolarsBackend",
    "PlanResourceResolver",
    "EntrypointLoader",
]
