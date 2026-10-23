"""Argument type names and helpers for spec function arguments."""

from __future__ import annotations

import typing

DATAFRAME: typing.Final[str] = "dataframe"
STRING: typing.Final[str] = "string"
INTEGER: typing.Final[str] = "integer"
FLOAT: typing.Final[str] = "float"
BOOLEAN: typing.Final[str] = "boolean"
ARRAY: typing.Final[str] = "array"
OBJECT: typing.Final[str] = "object"

AtomicArgumentType = typing.Literal[
    "dataframe", "string", "integer", "float", "boolean", "array", "object"
]
ATOMIC_ARGUMENT_TYPES: typing.Final[tuple[AtomicArgumentType, ...]] = typing.get_args(
    AtomicArgumentType
)


def array_of(item_type: str) -> str:
    """Return the spec expression for an array with homogeneous item types."""
    return f"{ARRAY}[{item_type}]"


def object_values_of(value_type: str) -> str:
    """Return the spec expression for a string-keyed object with homogeneous values."""
    return f"{OBJECT}{{str: {value_type}}}"


def array_item_type(type_expression: str) -> str | None:
    """Return the item type from an array expression, if it is homogeneous."""
    prefix = f"{ARRAY}["
    if type_expression.startswith(prefix) and type_expression.endswith("]"):
        item_type = type_expression[len(prefix) : -1]
        return item_type or None
    return None


def object_value_type(type_expression: str) -> str | None:
    """Return the value type from a homogeneous string-keyed object expression."""
    prefix = f"{OBJECT}{{str: "
    if type_expression.startswith(prefix) and type_expression.endswith("}"):
        value_type = type_expression[len(prefix) : -1]
        return value_type or None
    return None


__all__ = [
    "ARRAY",
    "ATOMIC_ARGUMENT_TYPES",
    "AtomicArgumentType",
    "BOOLEAN",
    "DATAFRAME",
    "FLOAT",
    "INTEGER",
    "OBJECT",
    "STRING",
    "array_item_type",
    "array_of",
    "object_value_type",
    "object_values_of",
]
