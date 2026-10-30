"""Function kind definitions and their spec-level execution rules."""

from __future__ import annotations

import dataclasses
import types
import typing

from . import arg_types

FunctionKindId = typing.Literal[
    "write", "read", "escape", "conform", "expand", "collapse", "vectorize"
]
ReturnKind = typing.Literal["dataframe", "none", "any"]
FunctionRole = typing.Literal["source", "transform", "sink", "effect"]


@dataclasses.dataclass(frozen=True)
class FunctionKind:
    """Definition of one built-in function kind and its declarative contract."""

    id: FunctionKindId
    dataframe_inputs: int | None
    returns: ReturnKind
    produces_features: bool
    role: FunctionRole


WRITE: typing.Final[FunctionKindId] = "write"
READ: typing.Final[FunctionKindId] = "read"
ESCAPE: typing.Final[FunctionKindId] = "escape"
CONFORM: typing.Final[FunctionKindId] = "conform"
EXPAND: typing.Final[FunctionKindId] = "expand"
COLLAPSE: typing.Final[FunctionKindId] = "collapse"
VECTORIZE: typing.Final[FunctionKindId] = "vectorize"

FUNCTION_KINDS: typing.Final[typing.Mapping[FunctionKindId, FunctionKind]] = types.MappingProxyType(
    {
        WRITE: FunctionKind(WRITE, 1, "none", False, "sink"),
        READ: FunctionKind(READ, 0, arg_types.DATAFRAME, True, "source"),
        ESCAPE: FunctionKind(ESCAPE, None, "any", True, "effect"),
        CONFORM: FunctionKind(CONFORM, 1, arg_types.DATAFRAME, True, "source"),
        EXPAND: FunctionKind(EXPAND, 1, arg_types.DATAFRAME, True, "source"),
        COLLAPSE: FunctionKind(COLLAPSE, 1, arg_types.DATAFRAME, True, "source"),
        VECTORIZE: FunctionKind(VECTORIZE, 1, arg_types.DATAFRAME, True, "transform"),
    }
)


def kind_hint(returns: ReturnKind, dataframe_inputs: int) -> str:
    """Suggest explicitly declared kinds matching a function contract."""
    matches = [
        kind
        for kind, definition in FUNCTION_KINDS.items()
        if kind != ESCAPE
        and definition.returns == returns
        and definition.dataframe_inputs == dataframe_inputs
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
    "ESCAPE",
    "EXPAND",
    "FUNCTION_KINDS",
    "FunctionKind",
    "FunctionKindId",
    "FunctionRole",
    "READ",
    "ReturnKind",
    "VECTORIZE",
    "WRITE",
    "kind_hint",
]
