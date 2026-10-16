"""Dimension, dataset identity, and ordering validation."""

from __future__ import annotations

import typing

from uptimely import contracts

from . import context as context_module
from . import errors

__all__ = [
    "_validate_dataset_order",
    "_validate_dimensions",
    "_validate_entity_dimensions",
    "validate_dataset_ids",
]


def _validate_dimensions(validation_context: context_module.AnalyticsValidationContext) -> set[str]:
    """Validate dimension parents and return declared dimension identifiers."""
    model = validation_context.model
    dimensions = set(validation_context.dimension_ids)
    for dimension_id, dimension in model.dimensions.items():
        if dimension.parent is not None and dimension.parent not in dimensions:
            raise ValueError(
                f"Dimension {dimension_id} references unknown parent: {dimension.parent}"
            )
        lineage: list[str] = []
        current = dimension_id
        while current is not None:
            if current in lineage:
                cycle = lineage[lineage.index(current) :] + [current]
                raise errors.AnalyticsError(
                    "Dimension parent cycle: " + " -> ".join(cycle),
                    code="dimension_parent_cycle",
                    path=("dimensions", dimension_id, "parent"),
                )
            lineage.append(current)
            current_dimension = model.dimensions.get(current)
            current = current_dimension.parent if current_dimension is not None else None
    return dimensions


def validate_dataset_ids(
    model: typing.Any | context_module.AnalyticsValidationContext,
) -> None:
    """Require dataset identifiers to be globally unambiguous."""
    if isinstance(model, context_module.AnalyticsValidationContext):
        duplicate = model.first_duplicate_dataset()
        if duplicate is None:
            return
        first, repeated = duplicate
        raise errors.AnalyticsError(
            f"Duplicate dataset id {repeated.dataset.id}; "
            f"already declared by entity {first.entity_id}",
            code="duplicate_dataset_id",
            path=("entities", repeated.entity_id, "datasets", repeated.dataset.id),
        )

    owners: dict[str, str] = {}
    for entity_id, entity in model.entities.items():
        for dataset in entity.datasets:
            owner = owners.get(dataset.id)
            if owner is not None:
                raise errors.AnalyticsError(
                    f"Duplicate dataset id {dataset.id}; already declared by entity {owner}",
                    code="duplicate_dataset_id",
                    path=("entities", entity_id, "datasets", dataset.id),
                )
            owners[dataset.id] = entity_id


def _validate_entity_dimensions(
    validation_context: context_module.AnalyticsValidationContext, dimensions: set[str]
) -> None:
    """Validate that entities refer only to declared dimensions."""
    model = validation_context.model
    for entity_id, entity in model.entities.items():
        unknown_dimensions = sorted(set(entity.dimension_ids) - dimensions)
        if unknown_dimensions:
            raise ValueError(
                f"Entity {entity_id} references unknown dimensions: "
                + ", ".join(unknown_dimensions)
            )


def _validate_dataset_order(validation_context: context_module.AnalyticsValidationContext) -> None:
    """Require distinct ordering keys belonging to the dataset's entity."""
    model = validation_context.model
    for entity_id, entity in model.entities.items():
        dimensions = set(entity.dimension_ids)
        for dataset in entity.datasets:
            seen: set[str] = set()
            for index, key in enumerate(dataset.order):
                dimension = key.dimension.removeprefix(contracts.DIMENSION_PREFIX)
                path = ("entities", entity_id, "datasets", dataset.id, "order", index, "dimension")
                if dimension not in dimensions:
                    raise errors.AnalyticsError(
                        f"Dataset {dataset.id} order references a dimension not declared "
                        f"by entity {entity_id}: {dimension}",
                        code="invalid_order_dimension",
                        path=path,
                    )
                if dimension in seen:
                    raise errors.AnalyticsError(
                        f"Dataset {dataset.id} order repeats dimension: {dimension}",
                        code="duplicate_order_dimension",
                        path=path,
                    )
                seen.add(dimension)
