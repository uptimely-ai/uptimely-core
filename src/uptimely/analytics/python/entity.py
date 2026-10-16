"""Python-friendly entity declaration."""

from __future__ import annotations

import dataclasses

from uptimely.analytics import model as analytics_model

from . import dataset as dataset_module
from . import dimension as dimension_module

__all__ = [
    "Entity",
]


@dataclasses.dataclass(frozen=True)
class Entity:
    """A named entity containing datasets and their dimensions."""

    id: str
    name: str
    dimensions: list[dimension_module.Dimension]
    datasets: list[dataset_module.Dataset]
    description: str | None = None

    def to_model(self) -> analytics_model.Entity:
        """Convert this entity declaration to its JSON model."""
        return analytics_model.Entity(
            id=self.id,
            name=self.name,
            description=self.description,
            dimensions=[dimension.to_model() for dimension in self.dimensions],
            datasets=[dataset.to_model() for dataset in self.datasets],
        )
