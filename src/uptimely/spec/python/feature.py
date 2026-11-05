"""Python-friendly dataset feature declarations."""

from __future__ import annotations

import dataclasses

from uptimely.spec import model as spec_model
from uptimely.spec.model import common as spec_common

__all__ = ["Feature", "FeatureSet"]


@dataclasses.dataclass(frozen=True)
class Feature:
    """A named output feature with a stable identifier and display name."""

    id: str
    name: str | None = None
    type: str | None = None
    unit: str | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        """Generate a display name from the ID when one is not supplied."""
        if self.name is None:
            object.__setattr__(self, "name", spec_common.humanize_identifier(self.id))

    def to_model(self) -> spec_model.Feature:
        """Convert this feature declaration to its JSON model."""
        return spec_model.Feature(
            id=self.id,
            name=self.name,
            description=self.description,
            type=self.type,
            unit=self.unit,
        )


class FeatureSet:
    """Namespace for a profile's feature declarations.

    Subclasses declare :class:`Feature` instances as class attributes and
    reference those attributes from ``Action.outputs``.
    """
