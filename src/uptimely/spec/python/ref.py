"""Import-independent resource lookups for Python declarations."""

import typing

from uptimely.spec import arg_types, selectors

from . import references
from .function_reference import FunctionReference, function
from .references import ProfileGrainReference, Reference

__all__ = [
    "FunctionReference",
    "Reference",
    "ProfileGrainReference",
    "feature",
    "dimension",
    "profile",
    "dataset",
    "fragment",
    "params",
    "row_context",
    "function",
]


def feature(name: str) -> references.FeatureReference:
    """Reference a feature by ID, defaulting to its column identifier."""
    return references.FeatureReference(kind="feature", value=f"{selectors.FEATURE_PREFIX}{name}")


def dimension(name: str) -> references.DimensionReference:
    """Reference a dimension by ID."""
    return references.DimensionReference(
        kind=arg_types.STRING, value=f"{selectors.DIMENSION_PREFIX}{name}"
    )


def profile(name: str | None = None) -> references.ProfileReference:
    """Reference a named profile, or the current profile when omitted."""
    identifier = selectors.CURRENT_ID if name is None else name
    return references.ProfileReference(
        kind=arg_types.STRING, value=f"{selectors.PROFILE_PREFIX}{identifier}"
    )


def dataset(name: str | None = None) -> references.Reference:
    """Select a named profile's runtime dataset, or the current profile's dataset."""
    return profile(name).dataset


def fragment() -> references.Reference:
    """Select the current operator's staged fragment dataframe."""
    return references.Reference(
        kind=arg_types.DATAFRAME,
        value=f"{selectors.OPERATOR_PREFIX}{selectors.CURRENT_ID}.fragment",
    )


def row_context(attribute: typing.Literal["before", "after", "dimension"]) -> references.Reference:
    """Select a scalar attribute of the current operator's row context."""
    if attribute not in selectors.ROW_CONTEXT_ATTRIBUTES:
        raise ValueError(f"Unsupported row-context attribute: {attribute!r}")
    return references.Reference(
        kind=arg_types.OBJECT,
        value=f"{selectors.ROW_CONTEXT_PREFIX}{attribute}",
    )


def params(name: str) -> references.Params:
    """Reference a required configuration value without reading configuration."""
    return references.Params(name)
