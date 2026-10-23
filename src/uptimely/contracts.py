"""Shared contracts for spec function operations."""

import typing

FunctionOperation = typing.Literal[
    "read", "write", "escape", "vectorize", "collapse", "expand", "conform"
]
FUNCTION_OPERATIONS: typing.Final[tuple[FunctionOperation, ...]] = typing.get_args(
    FunctionOperation
)
READ, WRITE, ESCAPE, VECTORIZE, COLLAPSE, EXPAND, CONFORM = FUNCTION_OPERATIONS

FunctionReturns = typing.Literal["dataframe", "none", "any"]
FRAGMENT_OPERATIONS: tuple[FunctionOperation, ...] = (READ, CONFORM, EXPAND, COLLAPSE)

FEATURE_PREFIX = "$features."
DATASET_PREFIX = "$datasets."
DIMENSION_PREFIX = "$dimensions."
CURRENT_ID = "@"
ID_SELECTOR = ".id"
DATAFRAME_SELECTOR = ".dataframe"
STRUCTURAL_PREFIXES = (FEATURE_PREFIX, DATASET_PREFIX, DIMENSION_PREFIX)

DATAFRAME_INPUT_COUNTS: dict[FunctionOperation, int | None] = {
    READ: 0,
    COLLAPSE: 1,
    CONFORM: 2,
    EXPAND: 2,
    VECTORIZE: 1,
    WRITE: 1,
    ESCAPE: None,
}
OPERATION_RETURN_KINDS: dict[FunctionOperation, FunctionReturns] = {
    READ: "dataframe",
    WRITE: "none",
    ESCAPE: "any",
    VECTORIZE: "dataframe",
    COLLAPSE: "dataframe",
    EXPAND: "dataframe",
    CONFORM: "dataframe",
}

__all__ = [
    "COLLAPSE",
    "CONFORM",
    "CURRENT_ID",
    "DATAFRAME_SELECTOR",
    "DATAFRAME_INPUT_COUNTS",
    "DATASET_PREFIX",
    "DIMENSION_PREFIX",
    "ESCAPE",
    "EXPAND",
    "FEATURE_PREFIX",
    "FUNCTION_OPERATIONS",
    "FRAGMENT_OPERATIONS",
    "FunctionOperation",
    "FunctionReturns",
    "ID_SELECTOR",
    "OPERATION_RETURN_KINDS",
    "READ",
    "STRUCTURAL_PREFIXES",
    "VECTORIZE",
    "WRITE",
]
