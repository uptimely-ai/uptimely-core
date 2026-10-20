"""Atomic dimension declaration checks over prepared ancestry facts."""

from __future__ import annotations

from . import context as context_module
from . import errors


def validate_parent(
    item: context_module.DimensionParents, dimension_ids: frozenset[str]
) -> context_module.ValidationResult:
    """Require a dimension's parent to be declared."""
    if item.parent_id is not None and item.parent_id not in dimension_ids:
        return ValueError(
            f"Dimension {item.dimension_id} references unknown parent: {item.parent_id}"
        )
    return None


def validate_parent_cycle(item: context_module.DimensionParents) -> context_module.ValidationResult:
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
