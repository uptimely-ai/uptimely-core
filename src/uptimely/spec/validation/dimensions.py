"""Atomic dimension declaration checks over prepared ancestry facts."""

from __future__ import annotations

import collections.abc
import dataclasses

from uptimely.spec import model as spec_model

from . import context as context_module
from . import errors


@dataclasses.dataclass(frozen=True)
class DimensionParents:
    """A dimension's parent and any cycle reached by walking its ancestry."""

    dimension_id: str
    parent_id: str | None
    cycle: tuple[str, ...]


def iter_parent_declarations(
    model: spec_model.Spec,
) -> collections.abc.Iterator[DimensionParents]:
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


def validate_parent(
    item: DimensionParents, dimension_ids: frozenset[str]
) -> context_module.ValidationResult:
    """Require a dimension's parent to be declared."""
    if item.parent_id is not None and item.parent_id not in dimension_ids:
        return ValueError(
            f"Dimension {item.dimension_id} references unknown parent: {item.parent_id}"
        )
    return None


def validate_parent_cycle(item: DimensionParents) -> context_module.ValidationResult:
    """Reject a cycle in a dimension's ancestry."""
    if item.cycle:
        return errors.SpecError(
            "Dimension parent cycle: " + " -> ".join(item.cycle),
            code="dimension_parent_cycle",
            path=("dimensions", item.dimension_id, "parent"),
        )
    return None


def validate_entity_dimensions(
    entity_id: str, dimensions: frozenset[str], dimension_ids: frozenset[str]
) -> context_module.ValidationResult:
    """Require an entity's dimensions to be declared."""
    if not dimensions.issubset(dimension_ids):
        return ValueError(
            f"Entity {entity_id} references unknown dimensions: "
            + ", ".join(sorted(dimensions - dimension_ids))
        )
    return None
