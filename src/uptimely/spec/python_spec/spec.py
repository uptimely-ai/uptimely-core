"""Python-friendly specification declarations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from uptimely.spec.json_spec.json_model import FunctionCatalog

from .dataset import Dataset
from .dimension import Dimension
from .entity import Entity

__all__ = [
    "PythonSpecification",
]


@dataclass(frozen=True)
class PythonSpecification:
    """Build a canonical specification from Python authoring declarations."""

    entities: list[Entity] = field(default_factory=list)
    dimensions: list[Dimension] | dict[str, Dimension] | None = None
    name: str | None = None

    def iter_datasets(self) -> list[Dataset]:
        """Yield all dataset declarations owned by this specification."""
        if not self.entities:
            return []
        datasets: list[Dataset] = []
        for entity in self.entities:
            datasets.extend(entity.datasets)
        return datasets

    def function_catalog(self) -> FunctionCatalog:
        """Collect and merge the function catalog across all entities."""
        catalog = FunctionCatalog()
        for dataset in self.iter_datasets():
            dataset_catalog = dataset.function_catalog()
            for category in (
                "read",
                "write",
                "vectorize",
                "aggregate",
                "collapse",
                "expand",
                "conform",
            ):
                existing = dict(getattr(catalog, category, {}))
                incoming = dict(getattr(dataset_catalog, category, {}))
                for function_id, function_model in incoming.items():
                    if function_id in existing:
                        current = existing[function_id]
                        if getattr(current, "entrypoint", None) != getattr(
                            function_model, "entrypoint", None
                        ):
                            raise ValueError(
                                f"Conflicting function id '{function_id}' for {category}: "
                                f"{current.entrypoint} vs {function_model.entrypoint}"
                            )
                        continue
                    existing[function_id] = function_model
                setattr(catalog, category, existing)
        return catalog

    def to_spec_dict(self) -> dict[str, Any]:
        """Return the canonical specification dictionary for the configured entities."""
        from uptimely.spec.json_spec.json_functions import python_to_spec_dict

        return python_to_spec_dict(
            entities=self.entities,
            functions=self.function_catalog(),
            name=self.name,
            dimensions=self.dimensions,
        )
