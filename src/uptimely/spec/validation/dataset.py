"""Dataset identity and ordering validation.

The semantic phase order is coordinated by :mod:`uptimely.spec.validation.spec`.
"""

from __future__ import annotations

from uptimely import contracts

from .. import model as spec_model
from . import context as context_module
from . import errors


def validate_dataset_ids(model: spec_model.Spec) -> None:
    """Require dataset identifiers to be globally unambiguous."""
    owners: dict[str, str] = {}
    for entity_id, entity in model.entities.items():
        for dataset_model in entity.datasets:
            _validate_dataset_id(dataset_model.id, entity_id, owners)
            owners[dataset_model.id] = entity_id


def validate_order(validation_context: context_module.SpecValidationContext) -> None:
    """Require each dataset order to use distinct dimensions declared by its entity."""
    for entity_id, entity in validation_context.model.entities.items():
        entity_dimensions = set(entity.dimension_ids)
        for dataset_model in entity.datasets:
            seen_dimensions: set[str] = set()
            for index, key in enumerate(dataset_model.order):
                path = (
                    "entities",
                    entity_id,
                    "datasets",
                    dataset_model.id,
                    "order",
                    index,
                    "dimension",
                )
                dimension_id = key.dimension.removeprefix(contracts.DIMENSION_PREFIX)
                _validate_order_dimension_membership(
                    dataset_model.id, entity_id, dimension_id, entity_dimensions, path
                )
                _validate_unique_order_dimension(
                    dataset_model.id, dimension_id, seen_dimensions, path
                )
                seen_dimensions.add(dimension_id)


def _validate_dataset_id(dataset_id: str, entity_id: str, owners: dict[str, str]) -> None:
    """Require a dataset identifier to be globally unambiguous."""
    if dataset_id in owners:
        raise errors.SpecError(
            f"Duplicate dataset id {dataset_id}; already declared by entity {owners[dataset_id]}",
            code="duplicate_dataset_id",
            path=("entities", entity_id, "datasets", dataset_id),
        )


def _validate_order_dimension_membership(
    dataset_id: str,
    entity_id: str,
    dimension_id: str,
    entity_dimensions: set[str],
    path: tuple[str | int, ...],
) -> None:
    """Require an ordering dimension to be declared by its entity."""
    if dimension_id not in entity_dimensions:
        raise errors.SpecError(
            f"Dataset {dataset_id} order references a dimension not declared "
            f"by entity {entity_id}: {dimension_id}",
            code="invalid_order_dimension",
            path=path,
        )


def _validate_unique_order_dimension(
    dataset_id: str,
    dimension_id: str,
    seen_dimensions: set[str],
    path: tuple[str | int, ...],
) -> None:
    """Require each ordering dimension to appear only once."""
    if dimension_id in seen_dimensions:
        raise errors.SpecError(
            f"Dataset {dataset_id} order repeats dimension: {dimension_id}",
            code="duplicate_order_dimension",
            path=path,
        )
