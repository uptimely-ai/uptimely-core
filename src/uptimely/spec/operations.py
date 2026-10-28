"""Function kinds and their spec-level execution rules."""

from __future__ import annotations

import typing

from . import arg_types

FunctionKind = typing.Literal[
    "write", "read", "escape", "conform", "expand", "collapse", "vectorize"
]
FUNCTION_KINDS: typing.Final[tuple[FunctionKind, ...]] = typing.get_args(FunctionKind)
WRITE, READ, ESCAPE, CONFORM, EXPAND, COLLAPSE, VECTORIZE = FUNCTION_KINDS

FunctionReturns = typing.Literal["dataframe", "none", "any"]
FRAGMENT_KINDS: typing.Final[tuple[FunctionKind, ...]] = (
    READ,
    CONFORM,
    EXPAND,
    COLLAPSE,
)

KIND_DATAFRAME_INPUT_COUNTS: typing.Final[dict[FunctionKind, int | None]] = {
    READ: 0,
    COLLAPSE: 1,
    CONFORM: 1,
    EXPAND: 1,
    VECTORIZE: 1,
    WRITE: 1,
    ESCAPE: None,
}
KIND_RETURN_KINDS: typing.Final[dict[FunctionKind, FunctionReturns]] = {
    READ: arg_types.DATAFRAME,
    WRITE: "none",
    ESCAPE: "any",
    VECTORIZE: arg_types.DATAFRAME,
    COLLAPSE: arg_types.DATAFRAME,
    EXPAND: arg_types.DATAFRAME,
    CONFORM: arg_types.DATAFRAME,
}


def kind_hint(returns: FunctionReturns, dataframe_inputs: int) -> str:
    """Suggest explicitly declared kinds matching a function contract."""
    matches = [
        kind
        for kind in FUNCTION_KINDS
        if kind != ESCAPE
        and KIND_RETURN_KINDS[kind] == returns
        and KIND_DATAFRAME_INPUT_COUNTS[kind] == dataframe_inputs
    ]
    if matches:
        suggestions = ", ".join(matches)
        return (
            f" This function's declared return kind and {dataframe_inputs} dataframe "
            f"argument(s) fit kind(s): {suggestions}. Declare the intended "
            "kind explicitly."
        )
    return (
        f" No controlled kind matches this function's declared return kind and "
        f"{dataframe_inputs} dataframe argument(s). If it performs intentional "
        "uncontrolled work, declare kind=escape explicitly."
    )


__all__ = [
    "COLLAPSE",
    "CONFORM",
    "FUNCTION_KINDS",
    "FRAGMENT_KINDS",
    "FunctionKind",
    "KIND_DATAFRAME_INPUT_COUNTS",
    "ESCAPE",
    "EXPAND",
    "FunctionReturns",
    "KIND_RETURN_KINDS",
    "kind_hint",
    "READ",
    "VECTORIZE",
    "WRITE",
]
