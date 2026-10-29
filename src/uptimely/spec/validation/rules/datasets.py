"""Atomic dataset identity and ordering checks."""

from __future__ import annotations

import collections.abc
import dataclasses

from uptimely.spec import model as spec_model
from uptimely.spec import selectors
from uptimely.spec.validation import errors


@dataclasses.dataclass(frozen=True)
class DatasetDeclaration:
    """A declared dataset with its owning entity, dimensions, and spec path."""

    entity_id: str
    entity: spec_model.Entity
    dataset: spec_model.Dataset

    @property
    def dimensions(self) -> frozenset[str]:
        """Return the entity's current dimensions."""
        return frozenset(self.entity.dimension_ids)

    @property
    def key(self) -> tuple[str, str]:
        """Return the entity and dataset identity."""
        return self.entity_id, self.dataset.id

    @property
    def path(self) -> tuple[str, ...]:
        """Return the dataset's semantic path."""
        return ("entities", self.entity_id, "datasets", self.dataset.id)


def iter_datasets(spec: spec_model.Spec) -> collections.abc.Iterator[DatasetDeclaration]:
    """Yield dataset declarations with their owning entities and spec paths."""
    for entity_id, entity in spec.entities.items():
        for dataset in entity.datasets.values():
            yield DatasetDeclaration(entity_id, entity, dataset)


@dataclasses.dataclass(frozen=True)
class OrderDimension:
    """One order declaration with its normalized identifier and preceding keys."""

    location: DatasetDeclaration
    dimension_id: str
    preceding: frozenset[str]
    path: errors.SpecPath


def iter_order_dimensions(spec: spec_model.Spec) -> collections.abc.Iterator[OrderDimension]:
    """Yield normalized dataset order keys and their preceding dimensions."""
    for location in iter_datasets(spec):
        preceding: set[str] = set()
        for index, key in enumerate(location.dataset.order):
            dimension_id = key.dimension.removeprefix(selectors.DIMENSION_PREFIX)
            yield OrderDimension(
                location=location,
                dimension_id=dimension_id,
                preceding=frozenset(preceding),
                path=(*location.path, "order", index, "dimension"),
            )
            preceding.add(dimension_id)


def validate_dataset_ids(spec: spec_model.Spec) -> None:
    """Require globally unique dataset IDs."""
    seen: dict[str, DatasetDeclaration] = {}
    for location in iter_datasets(spec):
        previous = seen.get(location.dataset.id)
        if previous is not None:
            raise errors.SpecError(
                f"Duplicate dataset id {location.dataset.id}; already declared by entity "
                f"{previous.entity_id}",
                code="duplicate_dataset_id",
                path=location.path,
            )
        seen[location.dataset.id] = location


def validate_order_dimension(spec: spec_model.Spec) -> None:
    """Require an order dimension to be declared by its entity."""
    for item in iter_order_dimensions(spec):
        if item.dimension_id not in item.location.dimensions:
            raise errors.SpecError(
                f"Dataset {item.location.dataset.id} order references a dimension not declared "
                f"by entity {item.location.entity_id}: {item.dimension_id}",
                code="invalid_order_dimension",
                path=item.path,
            )


def validate_unique_order_dimension(spec: spec_model.Spec) -> None:
    """Reject a repeated order dimension."""
    for item in iter_order_dimensions(spec):
        if item.dimension_id in item.preceding:
            raise errors.SpecError(
                f"Dataset {item.location.dataset.id} order repeats dimension: {item.dimension_id}",
                code="duplicate_order_dimension",
                path=item.path,
            )
