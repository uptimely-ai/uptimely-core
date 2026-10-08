"""Python-friendly dimension declaration."""

from __future__ import annotations

from dataclasses import dataclass

from uptimely.spec.json_spec.json_model import Dimension as DimensionModel

__all__ = [
    "Dimension",
]


@dataclass(frozen=True)
class Dimension:
    """A reusable dataset-grain identifier."""

    id: str
    type: str
    description: str | None = None
    parent: str | None = None

    def to_model(self) -> DimensionModel:
        """Convert this dimension declaration to its JSON model."""
        return DimensionModel(
            id=self.id,
            type=self.type,
            description=self.description,
            parent=self.parent,
        )
