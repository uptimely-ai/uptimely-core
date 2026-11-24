"""Python-friendly dimension and resolution declarations."""

from __future__ import annotations

import dataclasses
from collections import abc

from uptimely.spec import model as spec_model
from uptimely.spec.model import base as model_base

__all__ = [
    "Dimension",
    "Resolution",
]


@dataclasses.dataclass(frozen=True, init=False)
class Resolution:
    """A dataframe key resolution within a dimension."""

    id: str
    key: str
    type: str
    parent: str | None = None
    _dimension: Dimension | None = dataclasses.field(default=None, repr=False, compare=False)
    name: str | None = dataclasses.field(default=None, kw_only=True)

    def __init__(
        self,
        id: str,
        key: str | None = None,
        type: str | None = None,
        parent: str | None = None,
        *,
        name: str | None = None,
        _dimension: Dimension | None = None,
    ) -> None:
        """Initialize a resolution and default its dataframe key to the ID."""
        if type is None:
            raise TypeError("Resolution.__init__() missing required argument: 'type'")
        object.__setattr__(self, "id", id)
        object.__setattr__(self, "key", id if key is None else key)
        object.__setattr__(self, "type", type)
        object.__setattr__(self, "parent", parent)
        object.__setattr__(self, "_dimension", _dimension)
        object.__setattr__(self, "name", name)

    @property
    def dimension(self) -> Dimension | None:
        """Return the owning dimension when selected through ``Dimension.resolution``."""
        return self._dimension

    def to_model(self) -> spec_model.Resolution:
        """Convert this resolution declaration to its document model."""
        return spec_model.Resolution(
            id=self.id,
            key=self.key,
            type=self.type,
            parent=self.parent,
            name=self.name,
        )


@dataclasses.dataclass(frozen=True)
class Dimension:
    """A logical dimension with its available dataframe-key resolutions."""

    id: str
    resolutions: abc.Sequence[Resolution]
    description: str | None = None
    name: str | None = None

    def resolution(self, name: str) -> Resolution:
        """Return a selected resolution by ID, associated with this dimension.

        Raises:
            ValueError: If the resolution is not declared in this dimension.
        """
        for resolution in self.resolutions:
            if resolution.id == name:
                return dataclasses.replace(resolution, _dimension=self)
        raise ValueError(f"Dimension '{self.id}' does not declare resolution '{name}'")

    def __post_init__(self) -> None:
        """Generate a display name from the ID when one is not supplied."""
        if self.name is None:
            object.__setattr__(self, "name", model_base.humanize_identifier(self.id))

    def to_model(self) -> spec_model.Dimension:
        """Convert this dimension declaration to its JSON model."""
        resolutions: dict[str, spec_model.Resolution] = {}
        for resolution in self.resolutions:
            if not isinstance(resolution, Resolution):
                raise TypeError("Dimension resolutions must contain Resolution declarations")
            if resolution.id in resolutions:
                raise ValueError(
                    f"Dimension '{self.id}' has duplicate resolution id '{resolution.id}'"
                )
            resolutions[resolution.id] = resolution.to_model()
        return spec_model.Dimension(
            id=self.id,
            name=self.name,
            description=self.description,
            resolutions=resolutions,
        )
