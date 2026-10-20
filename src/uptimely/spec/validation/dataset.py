"""Atomic dataset identity and order checks over prepared facts."""

from __future__ import annotations

from uptimely.spec import model as spec_model

from . import context as context_module
from . import errors


def validate_dataset_ids(model: spec_model.Spec) -> None:
    """Require globally unique dataset IDs through the standalone public API."""
    context = context_module.SpecValidationContext.build(model)
    error = validate_unique_id(context.duplicate_dataset)
    if error is not None:
        raise error


def validate_unique_id(
    duplicate: tuple[context_module.DatasetLocation, context_module.DatasetLocation] | None,
) -> context_module.ValidationResult:
    """Reject a repeated dataset declaration."""
    if duplicate is not None:
        location, previous = duplicate
        return errors.SpecError(
            f"Duplicate dataset id {location.dataset.id}; already declared by entity "
            f"{previous.entity_id}",
            code="duplicate_dataset_id",
            path=location.path,
        )
    return None


def validate_order_dimension(
    item: context_module.OrderDimension,
) -> context_module.ValidationResult:
    """Require an order dimension to be declared by its entity."""
    if item.dimension_id not in item.entity_dimensions:
        return errors.SpecError(
            f"Dataset {item.location.dataset.id} order references a dimension not declared "
            f"by entity {item.location.entity_id}: {item.dimension_id}",
            code="invalid_order_dimension",
            path=item.path,
        )
    return None


def validate_unique_order_dimension(
    item: context_module.OrderDimension,
) -> context_module.ValidationResult:
    """Reject a repeated order dimension."""
    if item.dimension_id in item.preceding:
        return errors.SpecError(
            f"Dataset {item.location.dataset.id} order repeats dimension: {item.dimension_id}",
            code="duplicate_order_dimension",
            path=item.path,
        )
    return None
