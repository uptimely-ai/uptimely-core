"""Function operations and their spec-level execution rules."""

from __future__ import annotations

import typing

from . import arg_types

FunctionOperation = typing.Literal[
    "read", "write", "escape", "vectorize", "collapse", "expand", "conform"
]
FUNCTION_OPERATIONS: typing.Final[tuple[FunctionOperation, ...]] = typing.get_args(
    FunctionOperation
)
READ, WRITE, ESCAPE, VECTORIZE, COLLAPSE, EXPAND, CONFORM = FUNCTION_OPERATIONS

FunctionReturns = typing.Literal["dataframe", "none", "any"]
FRAGMENT_OPERATIONS: typing.Final[tuple[FunctionOperation, ...]] = (
    READ,
    CONFORM,
    EXPAND,
    COLLAPSE,
)

DATAFRAME_INPUT_COUNTS: typing.Final[dict[FunctionOperation, int | None]] = {
    READ: 0,
    COLLAPSE: 1,
    CONFORM: 2,
    EXPAND: 2,
    VECTORIZE: 1,
    WRITE: 1,
    ESCAPE: None,
}
OPERATION_RETURN_KINDS: typing.Final[dict[FunctionOperation, FunctionReturns]] = {
    READ: arg_types.DATAFRAME,
    WRITE: "none",
    ESCAPE: "any",
    VECTORIZE: arg_types.DATAFRAME,
    COLLAPSE: arg_types.DATAFRAME,
    EXPAND: arg_types.DATAFRAME,
    CONFORM: arg_types.DATAFRAME,
}


def operation_hint(returns: FunctionReturns, dataframe_inputs: int) -> str:
    """Suggest explicitly declared operations matching a function contract."""
    matches = [
        operation
        for operation in FUNCTION_OPERATIONS
        if operation != ESCAPE
        and OPERATION_RETURN_KINDS[operation] == returns
        and DATAFRAME_INPUT_COUNTS[operation] == dataframe_inputs
    ]
    if matches:
        suggestions = ", ".join(matches)
        return (
            f" This function's declared return kind and {dataframe_inputs} dataframe "
            f"argument(s) fit operation(s): {suggestions}. Declare the intended "
            "operation explicitly."
        )
    return (
        f" No controlled operation matches this function's declared return kind and "
        f"{dataframe_inputs} dataframe argument(s). If it performs intentional "
        "uncontrolled work, declare operation=escape explicitly."
    )


__all__ = [
    "COLLAPSE",
    "CONFORM",
    "DATAFRAME_INPUT_COUNTS",
    "ESCAPE",
    "EXPAND",
    "FRAGMENT_OPERATIONS",
    "FUNCTION_OPERATIONS",
    "FunctionOperation",
    "FunctionReturns",
    "OPERATION_RETURN_KINDS",
    "operation_hint",
    "READ",
    "VECTORIZE",
    "WRITE",
]
