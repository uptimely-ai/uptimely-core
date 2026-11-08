"""Logical data types for profile features."""

from __future__ import annotations

import typing

STRING: typing.Final[str] = "string"
INTEGER: typing.Final[str] = "integer"
FLOAT: typing.Final[str] = "float"
NUMERIC: typing.Final[str] = "numeric"
BOOLEAN: typing.Final[str] = "boolean"
DATETIME: typing.Final[str] = "datetime"
DATE: typing.Final[str] = "date"
OBJECT: typing.Final[str] = "object"
ARRAY: typing.Final[str] = "array"

FeatureType = typing.Literal[
    "string",
    "integer",
    "float",
    "numeric",
    "boolean",
    "datetime",
    "date",
    "object",
    "array",
]
FEATURE_TYPES: typing.Final[tuple[FeatureType, ...]] = typing.get_args(FeatureType)

__all__ = [
    "ARRAY",
    "BOOLEAN",
    "DATE",
    "DATETIME",
    "FEATURE_TYPES",
    "FLOAT",
    "FeatureType",
    "INTEGER",
    "NUMERIC",
    "OBJECT",
    "STRING",
]
