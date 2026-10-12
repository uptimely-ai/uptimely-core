"""Python-friendly entity declaration."""

from __future__ import annotations

from dataclasses import dataclass

from uptimely.spec.json_spec import json_model

from .dataset import Dataset

__all__ = [
    "Entity",
]


@dataclass(frozen=True)
class Entity:
    """A named entity containing datasets and their dimensions."""

    id: str
    name: str
    dimensions: list[str]
    datasets: list[Dataset]
    description: str | None = None

    def to_model(self) -> json_model.Entity:
        """Convert this entity declaration to its JSON model."""
        return json_model.Entity(
            id=self.id,
            name=self.name,
            description=self.description,
            dimensions=self.dimensions,
            datasets=[
                json_model.Dataset(
                    id=dataset.id,
                    description=model.description,
                    row_scope=model.row_scope,
                    order=model.order,
                    features=model.features,
                    mappings=model.mappings,
                )
                for dataset in self.datasets
                for model in [dataset.to_model()]
            ],
        )
