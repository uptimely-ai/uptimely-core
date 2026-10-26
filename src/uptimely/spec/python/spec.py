"""Python-friendly spec declarations."""

from __future__ import annotations

import dataclasses
import functools
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
    """Build a spec document from dataset declarations and their entity attributes."""

    name: str | None = None
    _dataset_sources: abc.Sequence[type[dataset_module.Dataset] | dataset_module.Dataset] = (
        dataclasses.field(init=False, repr=False)
    )

    def __init__(
        self,
        datasets: abc.Sequence[type[dataset_module.Dataset] | dataset_module.Dataset],
        name: str | None = None,
    ) -> None:
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "_dataset_sources", datasets)

    @functools.cached_property
    def datasets(self) -> tuple[dataset_module.Dataset, ...]:
        """Instantiate dataset classes and validate their owning entities."""
        declarations: list[dataset_module.Dataset] = []
        if isinstance(self._dataset_sources, abc.Mapping):
            raise TypeError("datasets must be a sequence of Dataset classes or declarations")
        for item in self._dataset_sources:
            if isinstance(item, type) and issubclass(item, dataset_module.Dataset):
                declaration = item()
            elif isinstance(item, dataset_module.Dataset):
                declaration = item
            else:
                raise TypeError("datasets must contain Dataset classes or declarations")
            if not isinstance(declaration.entity, entity_module.Entity):
                raise ValueError(f"Dataset '{declaration.id}' must declare an entity")
            declarations.append(declaration)
        return tuple(declarations)

    @property
    def entities(self) -> list[entity_module.Entity]:
        """Return unique entity declarations with their associated datasets."""
        grouped: dict[str, tuple[entity_module.Entity, list[dataset_module.Dataset]]] = {}
        for declaration in self.datasets:
            entity = declaration.entity
            if not isinstance(entity, entity_module.Entity):
                raise ValueError(f"Dataset '{declaration.id}' must declare an entity")
            owner = dataclasses.replace(entity, datasets=[])
            if entity.id not in grouped:
                grouped[entity.id] = (owner, [])
            elif grouped[entity.id][0] != owner:
                raise ValueError(f"Datasets declare conflicting metadata for entity '{entity.id}'")
            grouped[entity.id][1].append(declaration)
        return [
            dataclasses.replace(entity, datasets=datasets) for entity, datasets in grouped.values()
        ]

    @property
    def dimensions(self) -> list[dimension.Dimension]:
        """Return unique dimensions declared by the dataset owners."""
        dimensions: dict[str, dimension.Dimension] = {}
        for entity in self.entities:
            for item in entity.dimensions:
                dimensions.setdefault(item.id, item)
        return list(dimensions.values())

    def iter_datasets(self) -> list[dataset_module.Dataset]:
        """Return datasets in entity and declaration order."""
        return list(self.datasets)

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
