"""Python-friendly entity declaration."""

from __future__ import annotations

import dataclasses

from uptimely.spec import model as spec_model

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
    dimensions: list[str | dimension_module.Dimension]
    datasets: list[dataset_module.Dataset] = dataclasses.field(default_factory=list)
    description: str | None = None

    def __hash__(self) -> int:
        """Hash an entity declaration by its canonical identifier."""
        return hash(self.id)

    def to_model(self) -> spec_model.Entity:
        """Convert this entity declaration to its JSON model."""
        dimensions: list[spec_model.Dimension] = []
        for dimension in self.dimensions:
            if isinstance(dimension, str):
                raise ValueError(
                    "Resolve dimension IDs through PythonSpec before converting an entity"
                )
            dimensions.append(dimension.to_model())
        return spec_model.Entity(
            id=self.id,
            name=self.name,
            description=self.description,
            dimensions=dimensions,
            datasets=dataset_module.to_models(self.datasets),
        )
