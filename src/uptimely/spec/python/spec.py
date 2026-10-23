"""Python-friendly spec declarations."""

from __future__ import annotations

import dataclasses
import typing
from collections import abc

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
    """Build a spec document from entity-to-dataset declarations."""

    datasets: abc.Mapping[entity_module.Entity, abc.Sequence[dataset_module.Dataset]]
    name: str | None = None

    @property
    def entities(self) -> list[entity_module.Entity]:
        """Return entity declarations with their associated datasets."""
        return [
            dataclasses.replace(entity, datasets=list(datasets))
            for entity, datasets in self.datasets.items()
        ]

    @property
    def dimensions(self) -> list[dimension.Dimension]:
        """Return unique dimensions declared by the dataset owners."""
        dimensions: dict[str, dimension.Dimension] = {}
        for entity in self.datasets:
            for item in entity.dimensions:
                dimensions.setdefault(item.id, item)
        return list(dimensions.values())

    def iter_datasets(self) -> list[dataset_module.Dataset]:
        """Return datasets in entity and declaration order."""
        datasets: list[dataset_module.Dataset] = []
        for entity_datasets in self.datasets.values():
            datasets.extend(entity_datasets)
        return datasets

    def function_catalog(self) -> spec_model.FunctionCatalog:
        """Collect and merge the function catalog across all datasets."""
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
