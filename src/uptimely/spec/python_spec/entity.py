"""Python-friendly entity declaration."""

from __future__ import annotations

from dataclasses import dataclass

from uptimely.spec.json_spec.json_model import (
    Dataset as DatasetModel,
)
from uptimely.spec.json_spec.json_model import (
    Entity as EntityModel,
)

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

    def to_model(self) -> EntityModel:
        """Convert this entity declaration to its JSON model."""
        return EntityModel(
            id=self.id,
            name=self.name,
            description=self.description,
            dimensions=self.dimensions,
            datasets=[
                DatasetModel(
                    id=dataset.id,
                    description=model.description,
                    row_scope=model.row_scope,
                    read=model.read,
                    conform=model.conform,
                    expand=model.expand,
                    collapse=model.collapse,
                    vectorize=model.vectorize,
                    write=model.write,
                )
                for dataset in self.datasets
                for model in [dataset.to_model()]
            ],
        )
