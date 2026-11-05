"""Import-independent resource lookups for Python declarations."""

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
    "data",
    "params",
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


def data(name: str | None = None) -> references.Reference:
    """Select a named profile's runtime data, or the current profile's data."""
    return profile(name).data


def params(name: str) -> references.Params:
    """Reference a required configuration value without reading configuration."""
    return references.Params(name)
