"""Execution engine and runtime adapters for portable plans."""

from .backend import (
    CallableLoader,
    DataFrameBackend,
    PlanResourceResolver,
    PolarsBackend,
    ResourceResolver,
)
from .config import EngineConfig
from .engine import Engine
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
]
