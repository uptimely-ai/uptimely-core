"""Python-friendly spec declarations."""

from __future__ import annotations

import copy
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
    """Build a spec from explicitly registered dimensions, entities, and datasets.

    Args:
        dimensions: Shared dimensions, including those referenced as objects.
        entities: Entity metadata with dimension IDs or Dimension objects.
        datasets: Dataset classes or instances with entity IDs or Entity objects.
        name: Optional spec display name.
    """

    name: str | None = None
    _dataset_sources: abc.Sequence[type[dataset_module.Dataset] | dataset_module.Dataset] = (
        dataclasses.field(init=False, repr=False)
    )
    _dimension_sources: abc.Sequence[dimension.Dimension] = dataclasses.field(
        init=False, repr=False
    )
    _entity_sources: abc.Sequence[entity_module.Entity] = dataclasses.field(init=False, repr=False)

    def __init__(
        self,
        dimensions: abc.Sequence[dimension.Dimension],
        entities: abc.Sequence[entity_module.Entity],
        datasets: abc.Sequence[type[dataset_module.Dataset] | dataset_module.Dataset],
        name: str | None = None,
    ) -> None:
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "_dimension_sources", dimensions)
        object.__setattr__(self, "_entity_sources", entities)
        object.__setattr__(self, "_dataset_sources", datasets)

    @functools.cached_property
    def dimensions(self) -> list[dimension.Dimension]:
        """Return explicitly registered dimensions, rejecting duplicate IDs."""
        if not isinstance(self._dimension_sources, abc.Sequence):
            raise TypeError("dimensions must be a sequence of Dimension declarations")
        registered: dict[str, dimension.Dimension] = {}
        for item in self._dimension_sources:
            if not isinstance(item, dimension.Dimension):
                raise TypeError("dimensions must contain Dimension declarations")
            if item.id in registered:
                raise ValueError(f"Duplicate dimension id {item.id}")
            registered[item.id] = item
        return list(registered.values())

    @functools.cached_property
    def _registered_entities(self) -> dict[str, entity_module.Entity]:
        if not isinstance(self._entity_sources, abc.Sequence):
            raise TypeError("entities must be a sequence of Entity declarations")
        registered: dict[str, entity_module.Entity] = {}
        for owner in self._entity_sources:
            if not isinstance(owner, entity_module.Entity):
                raise TypeError("entities must contain Entity declarations")
            if owner.id in registered:
                raise ValueError(f"Duplicate entity id {owner.id}")
            registered[owner.id] = self._resolve_entity(owner)
        return registered

    def _resolve_entity(self, owner: entity_module.Entity) -> entity_module.Entity:
        dimensions = {item.id: item for item in self.dimensions}
        resolved: list[str | dimension.Dimension] = []
        for item in owner.dimensions:
            if not isinstance(item, (str, dimension.Dimension)):
                raise TypeError("entity dimensions must contain dimension IDs or declarations")
            identifier = item if isinstance(item, str) else item.id
            if identifier not in dimensions:
                raise ValueError(
                    f"Entity '{owner.id}' references undeclared dimension '{identifier}'"
                )
            if not isinstance(item, str) and item != dimensions[identifier]:
                raise ValueError(f"Conflicting metadata for dimension '{identifier}'")
            resolved.append(dimensions[identifier])
        return dataclasses.replace(owner, dimensions=resolved, datasets=[])

    @functools.cached_property
    def datasets(self) -> tuple[dataset_module.Dataset, ...]:
        """Instantiate dataset classes and validate their owning entities."""
        declarations: list[dataset_module.Dataset] = []
        if not isinstance(self._dataset_sources, abc.Sequence):
            raise TypeError("datasets must be a sequence of Dataset classes or declarations")
        identifiers: set[str] = set()
        for item in self._dataset_sources:
            if isinstance(item, type) and issubclass(item, dataset_module.Dataset):
                declaration = item()
            elif isinstance(item, dataset_module.Dataset):
                declaration = item
            else:
                raise TypeError("datasets must contain Dataset classes or declarations")
            owner = declaration.entity
            if not isinstance(owner, (str, entity_module.Entity)):
                raise ValueError(f"Dataset '{declaration.id}' must declare an entity")
            identifier = owner if isinstance(owner, str) else owner.id
            if identifier not in self._registered_entities:
                raise ValueError(
                    f"Dataset '{declaration.id}' references undeclared entity '{identifier}'"
                )
            if (
                not isinstance(owner, str)
                and self._resolve_entity(owner) != self._registered_entities[identifier]
            ):
                raise ValueError(f"Conflicting metadata for entity '{identifier}'")
            if declaration.id in identifiers:
                raise ValueError(f"Duplicate dataset id {declaration.id}")
            identifiers.add(declaration.id)
            declarations.append(declaration)
        return tuple(declarations)

    @property
    def entities(self) -> list[entity_module.Entity]:
        """Resolve registered entities and associate explicitly registered datasets."""
        grouped: dict[str, list[dataset_module.Dataset]] = {
            identifier: [] for identifier in self._registered_entities
        }
        for declaration in self.datasets:
            owner = declaration.entity
            if not isinstance(owner, (str, entity_module.Entity)):
                raise ValueError(f"Dataset '{declaration.id}' must declare an entity")
            identifier = owner if isinstance(owner, str) else owner.id
            resolved = copy.copy(declaration)
            resolved.entity = self._registered_entities[identifier]
            grouped[identifier].append(resolved)
        return [
            dataclasses.replace(owner, datasets=grouped[identifier])
            for identifier, owner in self._registered_entities.items()
        ]

    def iter_datasets(self) -> list[dataset_module.Dataset]:
        """Return datasets in explicit registration order."""
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
