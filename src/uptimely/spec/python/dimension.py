"""Python-friendly dimension declaration."""

from __future__ import annotations

import dataclasses

from uptimely.spec import model as spec_model

__all__ = [
    "Dimension",
]


@dataclasses.dataclass(frozen=True)
class Dimension:
    """A reusable dataset-grain identifier."""

    id: str
    type: str
    description: str | None = None
    parent: str | None = None

    def to_model(self) -> spec_model.Dimension:
        """Convert this dimension declaration to its JSON model."""
        return spec_model.Dimension(
            id=self.id,
            type=self.type,
            description=self.description,
            parent=self.parent,
        )
