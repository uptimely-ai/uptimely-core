"""Atomic dataset identity and ordering checks."""

from __future__ import annotations

import collections.abc
import dataclasses

from uptimely.spec import model as spec_model
from uptimely.spec import selectors

from . import errors, traversal


@dataclasses.dataclass(frozen=True)
class OrderDimension:
    """One order declaration with its normalized identifier and preceding keys."""

    location: traversal.DatasetLocation
    dimension_id: str
    entity_dimensions: frozenset[str]
    preceding: frozenset[str]
    path: traversal.SpecPath


def iter_order_dimensions(
    datasets: collections.abc.Iterable[traversal.DatasetLocation],
) -> collections.abc.Iterator[OrderDimension]:
    """Yield normalized dataset order keys and their preceding dimensions."""
    for location in datasets:
        preceding: set[str] = set()
        for index, key in enumerate(location.dataset.order):
            dimension_id = key.dimension.removeprefix(selectors.DIMENSION_PREFIX)
            yield OrderDimension(
                location=location,
                dimension_id=dimension_id,
                entity_dimensions=location.dimensions,
                preceding=frozenset(preceding),
                path=(*location.path, "order", index, "dimension"),
            )
            preceding.add(dimension_id)


def validate_dataset_ids(spec: spec_model.Spec) -> None:
    """Require globally unique dataset IDs."""
    seen: dict[str, traversal.DatasetLocation] = {}
    for location in traversal.iter_datasets(spec):
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
    for item in iter_order_dimensions(traversal.iter_datasets(spec)):
        if item.dimension_id not in item.entity_dimensions:
            raise errors.SpecError(
                f"Dataset {item.location.dataset.id} order references a dimension not declared "
                f"by entity {item.location.entity_id}: {item.dimension_id}",
                code="invalid_order_dimension",
                path=item.path,
            )


def validate_unique_order_dimension(spec: spec_model.Spec) -> None:
    """Reject a repeated order dimension."""
    for item in iter_order_dimensions(traversal.iter_datasets(spec)):
        if item.dimension_id in item.preceding:
            raise errors.SpecError(
                f"Dataset {item.location.dataset.id} order repeats dimension: {item.dimension_id}",
                code="duplicate_order_dimension",
                path=item.path,
            )
