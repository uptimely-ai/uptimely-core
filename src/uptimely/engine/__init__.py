"""Execution engine and runtime adapters for portable plans."""

from .config import Config, EngineBackendConfig, EngineConfig, ParameterConfig, Params
from .dataframe.backend import DataFrameBackend, PolarsBackend
from .dataframe.dataset import Dataset
from .dataframe.fragment import Fragment
from .engine import Engine
from .runtime.result import ExecutionResult

__all__ = [
    "Engine",
    "Config",
    "EngineConfig",
    "Params",
    "ParameterConfig",
    "EngineBackendConfig",
    "ExecutionResult",
    "DataFrameBackend",
    "PolarsBackend",
    "Dataset",
    "Fragment",
]
