"""Execution engine and runtime adapters for portable plans."""

from .config import EngineBackendConfig, EngineConfig
from .dataframe.backend import DataFrameBackend, PolarsBackend
from .engine import Engine
from .runtime.result import ExecutionResult

__all__ = [
    "Engine",
    "EngineConfig",
    "EngineBackendConfig",
    "ExecutionResult",
    "DataFrameBackend",
    "PolarsBackend",
]
