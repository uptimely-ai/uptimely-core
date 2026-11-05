"""Structural reference prefixes and selectors used by the spec format."""

from __future__ import annotations

import typing

REFERENCE_PREFIX: typing.Final[str] = "$"
FEATURE_PREFIX: typing.Final[str] = f"{REFERENCE_PREFIX}features."
PROFILE_PREFIX: typing.Final[str] = f"{REFERENCE_PREFIX}profiles."
DIMENSION_PREFIX: typing.Final[str] = f"{REFERENCE_PREFIX}dimensions."
PARAMS_PREFIX: typing.Final[str] = f"{REFERENCE_PREFIX}params."
CURRENT_ID: typing.Final[str] = "@"
ID_SELECTOR: typing.Final[str] = ".id"
DATAFRAME_SELECTOR: typing.Final[str] = ".dataframe"
PROFILE_GRAIN_IDS_SELECTOR: typing.Final[str] = ".grain.ids"
STRUCTURAL_PREFIXES: typing.Final[tuple[str, ...]] = (
    FEATURE_PREFIX,
    PROFILE_PREFIX,
    DIMENSION_PREFIX,
)


def structural_identifier(value: str, prefix: str) -> str:
    """Return a structural reference's resource ID without its selector suffix."""
    return value.removeprefix(prefix).partition(".")[0]


__all__ = [
    "CURRENT_ID",
    "DATAFRAME_SELECTOR",
    "PROFILE_PREFIX",
    "PROFILE_GRAIN_IDS_SELECTOR",
    "DIMENSION_PREFIX",
    "PARAMS_PREFIX",
    "FEATURE_PREFIX",
    "ID_SELECTOR",
    "REFERENCE_PREFIX",
    "STRUCTURAL_PREFIXES",
    "structural_identifier",
]
