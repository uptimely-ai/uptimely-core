"""Typed deferred resource selectors for Python bindings."""

from __future__ import annotations

import dataclasses

from uptimely.spec import arg_types, selectors


@dataclasses.dataclass(frozen=True)
class Reference:
    """A portable selector and its binding value kind."""

    kind: str
    value: str

    def to_model(self) -> str:
        """Return the document selector."""
        return self.value

    def _attribute(self, name: str) -> Reference:
        return Reference(kind=arg_types.STRING, value=f"{self.value}.{name}")

    @property
    def id(self) -> Reference:
        """Select an identifier without introducing a data dependency."""
        return self._attribute("id")


class FeatureReference(Reference):
    """A feature ID by default, or explicit feature metadata."""

    @property
    def name(self) -> Reference:
        """Select the display name."""
        return self._attribute("name")

    @property
    def unit(self) -> Reference:
        """Select the measurement unit."""
        return self._attribute("unit")

    @property
    def description(self) -> Reference:
        """Select the description."""
        return self._attribute("description")

    @property
    def type(self) -> Reference:
        """Select the logical feature type."""
        return self._attribute("type")


class DimensionReference(Reference):
    """A dimension ID and its scoped resolutions."""

    @property
    def name(self) -> Reference:
        """Select the display name."""
        return self._attribute("name")

    @property
    def description(self) -> Reference:
        """Select the description."""
        return self._attribute("description")

    def resolution(self, name: str) -> ResolutionReference:
        """Select a resolution within this dimension."""
        return ResolutionReference(kind=arg_types.STRING, value=f"{self.value}.resolutions.{name}")


class ResolutionReference(Reference):
    """A dimension-scoped resolution ID and its metadata."""

    @property
    def key(self) -> Reference:
        """Select the dataframe column name."""
        return self._attribute("key")

    @property
    def type(self) -> Reference:
        """Select the logical key type."""
        return self._attribute("type")

    @property
    def parent(self) -> Reference:
        """Select the parent resolution ID."""
        return self._attribute("parent")


class ProfileReference(Reference):
    """A profile ID with explicit data and metadata selectors."""

    def to_model(self) -> str:
        """Bind a profile's identity rather than implicitly selecting its data."""
        return f"{self.value}.id"

    @property
    def dataset(self) -> Reference:
        """Select the runtime dataset, retaining the portable document format."""
        return Reference(kind=arg_types.DATAFRAME, value=f"{self.value}.dataset")

    @property
    def grain(self) -> ProfileGrainReference:
        """Select profile grain metadata."""
        return ProfileGrainReference(value=f"{self.value}.grain")

    @property
    def name(self) -> Reference:
        """Select the display name."""
        return self._attribute("name")

    @property
    def description(self) -> Reference:
        """Select the description."""
        return self._attribute("description")

    @property
    def category(self) -> Reference:
        """Select the category."""
        return self._attribute("category")

    @property
    def scope(self) -> Reference:
        """Select the scope."""
        return self._attribute("scope")


@dataclasses.dataclass(frozen=True)
class ProfileGrainReference:
    """Grain selectors available on a profile reference."""

    value: str

    @property
    def ids(self) -> Reference:
        """Select dataframe key names in grain order."""
        return Reference(kind=arg_types.array_of(arg_types.STRING), value=f"{self.value}.ids")


@dataclasses.dataclass(frozen=True)
class Params:
    """A required configuration value resolved by the engine.

    Args:
        name: A nonempty Python identifier naming a configuration parameter.

    Raises:
        ValueError: If the parameter name is invalid.
    """

    name: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.isidentifier():
            raise ValueError("Parameter names must be nonempty Python identifiers")

    def to_model(self) -> str:
        """Return the runtime parameter selector."""
        return f"{selectors.PARAMS_PREFIX}{self.name}"


@dataclasses.dataclass(frozen=True)
class Paths:
    """A project path resolved by the engine.

    Args:
        name: A nonempty Python identifier naming a configured path.

    Raises:
        ValueError: If the path name is invalid.
    """

    name: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.isidentifier():
            raise ValueError("Path names must be nonempty Python identifiers")

    def to_model(self) -> str:
        """Return the runtime path selector."""
        return f"{selectors.PATHS_PREFIX}{self.name}"
