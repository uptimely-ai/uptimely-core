"""Python-friendly dimension declaration."""

from __future__ import annotations

import dataclasses

from uptimely.spec import model as spec_model
from uptimely.spec.model import common as spec_common

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
    name: str | None = None

    def __post_init__(self) -> None:
        """Generate a display name from the ID when one is not supplied."""
        if self.name is None:
            object.__setattr__(self, "name", spec_common.humanize_identifier(self.id))

    def to_model(self) -> spec_model.Dimension:
        """Convert this dimension declaration to its JSON model."""
        return spec_model.Dimension(
            id=self.id,
            name=self.name,
            type=self.type,
            description=self.description,
            parent=self.parent,
        )
