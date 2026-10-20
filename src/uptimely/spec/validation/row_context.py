"""Atomic row-context checks against the prepared input dataset."""

from __future__ import annotations

from . import context as context_module


def validate_dataset_order(item: context_module.RowContext) -> context_module.ValidationResult:
    """Require dataset order for directional row context."""
    if item.requires_order and not item.has_order:
        return ValueError(
            f"Mapping {item.mapping_id} directional row context requires dataset order"
        )
    return None


def validate_dimension(item: context_module.RowContext) -> context_module.ValidationResult:
    """Require the context dimension to belong to the input entity."""
    if item.dimension_reference is not None and item.dimension_id not in item.dimensions:
        return ValueError(
            f"Mapping {item.mapping_id} context dimension is not in the input entity: "
            f"{item.dimension_id}"
        )
    return None


def validate_dimension_type(item: context_module.RowContext) -> context_module.ValidationResult:
    """Require the context dimension type to match the requested measure."""
    if (
        item.dimension_reference is not None
        and item.expected_type is not None
        and item.actual_type != item.expected_type
    ):
        return ValueError(
            f"Mapping {item.mapping_id} context dimension must have type {item.expected_type}"
        )
    return None


def validate_dimension_order(item: context_module.RowContext) -> context_module.ValidationResult:
    """Require a directional context dimension to occur in dataset order."""
    if (
        item.dimension_reference is not None
        and item.requires_order
        and item.dimension_reference not in item.order_dimensions
    ):
        return ValueError(
            f"Mapping {item.mapping_id} context dimension must occur in dataset order"
        )
    return None
