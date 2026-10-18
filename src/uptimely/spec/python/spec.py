"""Python-friendly spec declarations."""

from __future__ import annotations

import dataclasses
import typing

from uptimely.spec import catalog as function_catalog
from uptimely.spec import model as spec_model

from . import conversion, dimension
from . import dataset as dataset_module
from . import entity as entity_module

__all__ = [
    "PythonSpec",
]


@dataclasses.dataclass(frozen=True)
class PythonSpec:
    """Build a spec document from Python authoring declarations."""

    entities: list[entity_module.Entity] = dataclasses.field(default_factory=list)
    dimensions: list[dimension.Dimension] | dict[str, dimension.Dimension] | None = None
    name: str | None = None

    def iter_datasets(self) -> list[dataset_module.Dataset]:
        """Yield all dataset declarations owned by this spec model."""
        if not self.entities:
            return []
        datasets: list[dataset_module.Dataset] = []
        for entity in self.entities:
            datasets.extend(entity.datasets)
        return datasets

    def function_catalog(self) -> spec_model.FunctionCatalog:
        """Collect and merge the function catalog across all entities."""
        functions = function_catalog.merge_function_catalogs(
            (dataset.function_catalog() for dataset in self.iter_datasets()),
        )
        return spec_model.FunctionCatalog(root=functions)

    def to_model(self) -> spec_model.Spec:
        """Return the spec document model without resolving entrypoints."""
        return conversion.to_model(
            entities=self.entities,
            functions=self.function_catalog(),
            name=self.name,
            dimensions=self.dimensions,
        )

    def to_dict(self) -> dict[str, typing.Any]:
        """Return the spec document as a dictionary."""
        return conversion.to_dict(
            entities=self.entities,
            functions=self.function_catalog(),
            name=self.name,
            dimensions=self.dimensions,
        )
