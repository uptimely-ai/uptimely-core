"""Python-friendly analytics declarations."""

from __future__ import annotations

import dataclasses
import typing

from uptimely.analytics import json as json_analytics
from uptimely.analytics.json import json_functions

from . import dataset as dataset_module
from . import dimension
from . import entity as entity_module

__all__ = [
    "PythonAnalytics",
]


@dataclasses.dataclass(frozen=True)
class PythonAnalytics:
    """Build canonical analytics from Python authoring declarations."""

    entities: list[entity_module.Entity] = dataclasses.field(default_factory=list)
    dimensions: list[dimension.Dimension] | dict[str, dimension.Dimension] | None = None
    name: str | None = None

    def iter_datasets(self) -> list[dataset_module.Dataset]:
        """Yield all dataset declarations owned by this analytics model."""
        if not self.entities:
            return []
        datasets: list[dataset_module.Dataset] = []
        for entity in self.entities:
            datasets.extend(entity.datasets)
        return datasets

    def function_catalog(self) -> json_analytics.json_model.FunctionCatalog:
        """Collect and merge the function catalog across all entities."""
        functions: dict[str, json_analytics.json_model.FunctionTemplate] = {}
        for dataset in self.iter_datasets():
            dataset_catalog = dataset.function_catalog()
            for function_id, function_model in dataset_catalog.root.items():
                current = functions.get(function_id)
                if current is not None:
                    if (
                        current.operation != function_model.operation
                        or current.entrypoint != function_model.entrypoint
                    ):
                        raise ValueError(
                            f"Conflicting function definition for '{function_id}': "
                            f"{current.operation}/{current.entrypoint} vs "
                            f"{function_model.operation}/{function_model.entrypoint}"
                        )
                    continue
                functions[function_id] = function_model
        return json_analytics.json_model.FunctionCatalog(root=functions)

    def to_analytics_dict(self) -> dict[str, typing.Any]:
        """Return the canonical analytics dictionary for the configured entities."""
        return json_functions.python_to_analytics_dict(
            entities=self.entities,
            functions=self.function_catalog(),
            name=self.name,
            dimensions=self.dimensions,
        )
