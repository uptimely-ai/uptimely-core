"""Dimension validation rules and traversal.

The semantic phase order is coordinated by :mod:`uptimely.spec.validation.spec`.
"""

from __future__ import annotations

from . import context as context_module
from . import errors


def validate_parents(validation_context: context_module.SpecValidationContext) -> set[str]:
    """Validate dimension parents and return the declared dimension identifiers."""
    model = validation_context.model
    declared_dimensions = set(validation_context.dimension_ids)
    for dimension_id, dimension in model.dimensions.items():
        _validate_parent_existence(dimension_id, dimension.parent, declared_dimensions)
        parent_chain: list[str] = []
        current_dimension_id: str | None = dimension_id
        while current_dimension_id is not None:
            _validate_parent_chain_repetition(dimension_id, current_dimension_id, parent_chain)
            parent_chain.append(current_dimension_id)
            current_dimension = model.dimensions.get(current_dimension_id)
            current_dimension_id = (
                current_dimension.parent if current_dimension is not None else None
            )
    return declared_dimensions


def validate_entity_dimensions(
    validation_context: context_module.SpecValidationContext,
    declared_dimensions: set[str],
) -> None:
    """Validate every entity's dimension declarations."""
    for entity_id, entity in validation_context.model.entities.items():
        _validate_entity_dimensions(entity_id, entity.dimension_ids, declared_dimensions)


def _validate_parent_existence(
    dimension_id: str, parent_id: str | None, declared_dimensions: set[str]
) -> None:
    """Require a dimension's parent to be declared."""
    if parent_id is not None and parent_id not in declared_dimensions:
        raise ValueError(f"Dimension {dimension_id} references unknown parent: {parent_id}")


def _validate_parent_chain_repetition(
    root_dimension_id: str, current_dimension_id: str, parent_chain: list[str]
) -> None:
    """Reject a dimension already encountered in the current parent chain."""
    if current_dimension_id in parent_chain:
        cycle = parent_chain[parent_chain.index(current_dimension_id) :] + [current_dimension_id]
        raise errors.SpecError(
            "Dimension parent cycle: " + " -> ".join(cycle),
            code="dimension_parent_cycle",
            path=("dimensions", root_dimension_id, "parent"),
        )


def _validate_entity_dimensions(
    entity_id: str, dimension_ids: list[str], declared_dimensions: set[str]
) -> None:
    """Require every dimension declared by an entity to exist."""
    unknown_dimensions = sorted(set(dimension_ids) - declared_dimensions)
    if unknown_dimensions:
        raise ValueError(
            f"Entity {entity_id} references unknown dimensions: " + ", ".join(unknown_dimensions)
        )
