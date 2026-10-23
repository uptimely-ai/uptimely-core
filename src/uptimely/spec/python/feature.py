"""Python-friendly dataset feature declarations."""

from __future__ import annotations

import dataclasses

from uptimely.spec import model as spec_model

__all__ = ["Feature"]


@dataclasses.dataclass(frozen=True)
class Feature:
    """A named output feature; its name becomes the canonical feature ID."""

    name: str
    type: str | None = None
    unit: str | None = None
    description: str | None = None

    def to_model(self) -> spec_model.Feature:
        """Convert this feature declaration to its JSON model."""
        return spec_model.Feature(
            id=self.name,
            description=self.description,
            type=self.type,
            unit=self.unit,
        )
