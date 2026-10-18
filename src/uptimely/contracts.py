"""Shared contracts for spec function operations."""

import typing

FUNCTION_OPERATIONS = (
    "read",
    "write",
    "vectorize",
    "collapse",
    "expand",
    "conform",
)
FunctionOperation = typing.Literal["read", "write", "vectorize", "collapse", "expand", "conform"]
FunctionReturns = typing.Literal["dataframe", "none"]
FRAGMENT_OPERATIONS: tuple[FunctionOperation, ...] = ("read", "conform", "expand", "collapse")

FEATURE_PREFIX = "$features."
DATASET_PREFIX = "$datasets."
DIMENSION_PREFIX = "$dimensions."
CURRENT_ID = "@"
ID_SELECTOR = ".id"
DATAFRAME_SELECTOR = ".dataframe"
STRUCTURAL_PREFIXES = (FEATURE_PREFIX, DATASET_PREFIX, DIMENSION_PREFIX)

DATAFRAME_INPUT_COUNTS: dict[FunctionOperation, int] = {
    "read": 0,
    "collapse": 1,
    "conform": 2,
    "expand": 2,
    "vectorize": 1,
    "write": 1,
}
OPERATION_RETURN_KINDS: dict[FunctionOperation, FunctionReturns] = {
    "read": "dataframe",
    "write": "none",
    "vectorize": "dataframe",
    "collapse": "dataframe",
    "expand": "dataframe",
    "conform": "dataframe",
}

__all__ = [
    "CURRENT_ID",
    "DATAFRAME_SELECTOR",
    "DATAFRAME_INPUT_COUNTS",
    "DATASET_PREFIX",
    "DIMENSION_PREFIX",
    "FEATURE_PREFIX",
    "FUNCTION_OPERATIONS",
    "FRAGMENT_OPERATIONS",
    "FunctionOperation",
    "FunctionReturns",
    "ID_SELECTOR",
    "OPERATION_RETURN_KINDS",
    "STRUCTURAL_PREFIXES",
]
