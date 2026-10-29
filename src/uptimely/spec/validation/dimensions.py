"""Atomic dimension reference, ancestry, and entity-membership checks."""

from __future__ import annotations

import collections.abc
import dataclasses

from uptimely.spec import model as spec_model

from . import errors


@dataclasses.dataclass(frozen=True)
class DimensionParents:
    """A dimension's parent and any cycle reached by walking its ancestry."""

    dimension_id: str
    parent_id: str | None
    cycle: tuple[str, ...]


def iter_parent_declarations(model: spec_model.Spec) -> collections.abc.Iterator[DimensionParents]:
    """Yield dimension parent facts in declaration order."""
    for dimension_id, dimension in model.dimensions.items():
        chain: list[str] = []
        current: str | None = dimension_id
        while current is not None and current not in chain:
            chain.append(current)
            declaration = model.dimensions.get(current)
            current = declaration.parent if declaration is not None else None
        cycle = tuple(chain[chain.index(current) :] + [current]) if current is not None else ()
        yield DimensionParents(dimension_id, dimension.parent, cycle)


def iter_entity_dimensions(
    model: spec_model.Spec,
) -> collections.abc.Iterator[tuple[str, frozenset[str]]]:
    """Yield normalized entity dimensions in declaration order."""
    return (
        (entity_id, frozenset(entity.dimension_ids)) for entity_id, entity in model.entities.items()
    )


def validate_parent(spec: spec_model.Spec) -> None:
    """Require a dimension's parent to be declared."""
    for dimension_id, dimension in spec.dimensions.items():
        if dimension.parent is not None and dimension.parent not in spec.dimensions:
            raise ValueError(
                f"Dimension {dimension_id} references unknown parent: {dimension.parent}"
            )


def validate_parent_cycle(spec: spec_model.Spec) -> None:
    """Reject a cycle in dimension ancestry after parent references are validated."""
    for item in iter_parent_declarations(spec):
        if item.cycle:
            raise errors.SpecError(
                "Dimension parent cycle: " + " -> ".join(item.cycle),
                code="dimension_parent_cycle",
                path=("dimensions", item.dimension_id, "parent"),
            )


def validate_entity_dimensions(spec: spec_model.Spec) -> None:
    """Require an entity's dimensions to be declared."""
    dimension_ids = frozenset(spec.dimensions)
    for entity_id, dimensions in iter_entity_dimensions(spec):
        if not dimensions.issubset(dimension_ids):
            raise ValueError(
                f"Entity {entity_id} references unknown dimensions: "
                + ", ".join(sorted(dimensions - dimension_ids))
            )
