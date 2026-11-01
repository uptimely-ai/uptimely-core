"""Structural reference prefixes and selectors used by the spec format."""

from __future__ import annotations

import typing

REFERENCE_PREFIX: typing.Final[str] = "$"
FEATURE_PREFIX: typing.Final[str] = f"{REFERENCE_PREFIX}features."
DATASET_PREFIX: typing.Final[str] = f"{REFERENCE_PREFIX}datasets."
DIMENSION_PREFIX: typing.Final[str] = f"{REFERENCE_PREFIX}dimensions."
PARAMS_PREFIX: typing.Final[str] = f"{REFERENCE_PREFIX}params."
CURRENT_ID: typing.Final[str] = "@"
ID_SELECTOR: typing.Final[str] = ".id"
DATAFRAME_SELECTOR: typing.Final[str] = ".dataframe"
DIMENSION_IDS_SELECTOR: typing.Final[str] = ".dimensions.ids"
STRUCTURAL_PREFIXES: typing.Final[tuple[str, ...]] = (
    FEATURE_PREFIX,
    DATASET_PREFIX,
    DIMENSION_PREFIX,
)


def structural_identifier(value: str, prefix: str) -> str:
    """Return a structural reference's resource ID without its selector suffix."""
    identifier = value.removeprefix(prefix)
    if prefix == DATASET_PREFIX:
        return (
            identifier.removesuffix(DIMENSION_IDS_SELECTOR)
            .removesuffix(DATAFRAME_SELECTOR)
            .removesuffix(ID_SELECTOR)
        )
    return identifier.removesuffix(ID_SELECTOR)


__all__ = [
    "CURRENT_ID",
    "DATAFRAME_SELECTOR",
    "DATASET_PREFIX",
    "DIMENSION_IDS_SELECTOR",
    "DIMENSION_PREFIX",
    "PARAMS_PREFIX",
    "FEATURE_PREFIX",
    "ID_SELECTOR",
    "REFERENCE_PREFIX",
    "STRUCTURAL_PREFIXES",
    "structural_identifier",
]
