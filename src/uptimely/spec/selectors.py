"""Structural reference prefixes and selectors used by the spec format."""

from __future__ import annotations

import typing

FEATURE_PREFIX: typing.Final[str] = "$features."
DATASET_PREFIX: typing.Final[str] = "$datasets."
DIMENSION_PREFIX: typing.Final[str] = "$dimensions."
CURRENT_ID: typing.Final[str] = "@"
ID_SELECTOR: typing.Final[str] = ".id"
DATAFRAME_SELECTOR: typing.Final[str] = ".dataframe"
STRUCTURAL_PREFIXES: typing.Final[tuple[str, ...]] = (
    FEATURE_PREFIX,
    DATASET_PREFIX,
    DIMENSION_PREFIX,
)

__all__ = [
    "CURRENT_ID",
    "DATAFRAME_SELECTOR",
    "DATASET_PREFIX",
    "DIMENSION_PREFIX",
    "FEATURE_PREFIX",
    "ID_SELECTOR",
    "STRUCTURAL_PREFIXES",
]
