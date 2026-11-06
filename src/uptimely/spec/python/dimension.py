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


@dataclasses.dataclass(frozen=True)
class Resolution:
    """A dataframe key resolution within a dimension."""

    id: str
    key: str
    type: str
    parent: str | None = None

    def to_model(self) -> spec_model.Resolution:
        """Convert this resolution declaration to its document model."""
        return spec_model.Resolution(
            id=self.id,
            key=self.key,
            type=self.type,
            parent=self.parent,
        )


@dataclasses.dataclass(frozen=True)
class Dimension:
    """A logical dimension with its available dataframe-key resolutions."""

    id: str
    resolutions: abc.Sequence[Resolution]
    description: str | None = None
    name: str | None = None

    def resolution(self, name: str) -> Resolution:
        """Return a declared resolution by ID.

        Raises:
            ValueError: If the resolution is not declared in this dimension.
        """
        for resolution in self.resolutions:
            if resolution.id == name:
                return resolution
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
