"""Execution engine and runtime adapters for portable plans."""

from .backend import (
    CallableLoader,
    DataFrameBackend,
    EntrypointLoader,
    PlanResourceResolver,
    PolarsBackend,
    ResourceResolver,
)
from .engine import Calculation, Engine, EngineConfig
from .result import ExecutionResult

__all__ = [
    "Calculation",
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
