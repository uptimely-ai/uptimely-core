"""Execution engine and runtime adapters for portable plans."""

from .backend import DataFrameBackend, PolarsBackend
from .config import EngineBackendConfig, EngineConfig
from .engine import Engine
from .result import ExecutionResult

__all__ = [
    "Engine",
    "EngineConfig",
    "EngineBackendConfig",
    "ExecutionResult",
    "DataFrameBackend",
    "PolarsBackend",
]
