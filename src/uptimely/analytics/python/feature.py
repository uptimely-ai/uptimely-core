"""Python-friendly dataset feature declarations."""

from __future__ import annotations

import dataclasses

from uptimely.analytics import model as analytics_model

__all__ = ["Feature"]


@dataclasses.dataclass(frozen=True)
class Feature:
    """Metadata for a dataset feature, independent of how it is produced."""

    id: str
    description: str | None = None
    type: str | None = None
    unit: str | None = None

    def to_model(self) -> analytics_model.Feature:
        """Convert this feature declaration to its JSON model."""
        return analytics_model.Feature(
            id=self.id,
            description=self.description,
            type=self.type,
            unit=self.unit,
        )
