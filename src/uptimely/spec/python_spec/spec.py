"""Python-friendly specification declarations."""

from __future__ import annotations

import dataclasses
import typing

from uptimely.spec import json_spec
from uptimely.spec.json_spec import json_functions

from . import dataset as dataset_module
from . import dimension
from . import entity as entity_module

__all__ = [
    "PythonSpecification",
]


@dataclasses.dataclass(frozen=True)
class PythonSpecification:
    """Build a canonical specification from Python authoring declarations."""

    entities: list[entity_module.Entity] = dataclasses.field(default_factory=list)
    dimensions: list[dimension.Dimension] | dict[str, dimension.Dimension] | None = None
    name: str | None = None

    def iter_datasets(self) -> list[dataset_module.Dataset]:
        """Yield all dataset declarations owned by this specification."""
        if not self.entities:
            return []
        datasets: list[dataset_module.Dataset] = []
        for entity in self.entities:
            datasets.extend(entity.datasets)
        return datasets

    def function_catalog(self) -> json_spec.json_model.FunctionCatalog:
        """Collect and merge the function catalog across all entities."""
        catalog = json_spec.json_model.FunctionCatalog()
        for dataset in self.iter_datasets():
            dataset_catalog = dataset.function_catalog()
            for category in (
                "read",
                "write",
                "vectorize",
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

    def to_spec_dict(self) -> dict[str, typing.Any]:
        """Return the canonical specification dictionary for the configured entities."""
        return json_functions.python_to_spec_dict(
            entities=self.entities,
            functions=self.function_catalog(),
            name=self.name,
            dimensions=self.dimensions,
        )
