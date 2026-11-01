"""Atomic row-context checks against the selected input dataset."""

from __future__ import annotations

from uptimely import row_context as row_context_model
from uptimely.spec import model as spec_model
from uptimely.spec import selectors


def validate_dataset_order(spec: spec_model.Spec) -> None:
    """Require dataset order for directional row context."""
    for key, action in spec.action_items:
        declaration = action.row_context
        if declaration is None or not declaration.requires_order:
            continue
        dataset = spec.get_row_context_dataset(key)
        if dataset is not None and not dataset.order:
            raise ValueError(f"Action {action.id} directional row context requires dataset order")


def validate_dimension(spec: spec_model.Spec) -> None:
    """Require the context dimension to belong to the input entity."""
    for key, action in spec.action_items:
        declaration = action.row_context
        if declaration is None or declaration.dimension is None:
            continue
        dimensions = spec.get_row_context_dimensions(key)
        dimension_id = declaration.dimension.removeprefix(selectors.DIMENSION_PREFIX)
        if dimensions is not None and dimension_id not in dimensions:
            raise ValueError(
                f"Action {action.id} context dimension is not in the input entity: {dimension_id}"
            )


def validate_dimension_type(spec: spec_model.Spec) -> None:
    """Require the context dimension type to match the requested measure."""
    for action in spec.actions:
        declaration = action.row_context
        if declaration is None or declaration.dimension is None:
            continue
        measures = {
            measure
            for direction in (declaration.before, declaration.after)
            if isinstance(direction, row_context_model.ContextExtent)
            for measure in direction.model_dump(exclude_none=True)
        }
        expected_type = ("datetime" if "time" in measures else "integer") if measures else None
        dimension_id = declaration.dimension.removeprefix(selectors.DIMENSION_PREFIX)
        dimension = spec.dimensions.get(dimension_id)
        if (
            expected_type is not None
            and dimension is not None
            and (dimension.type != expected_type)
        ):
            raise ValueError(f"Action {action.id} context dimension must have type {expected_type}")


def validate_dimension_order(spec: spec_model.Spec) -> None:
    """Require a directional context dimension to occur in dataset order."""
    for key, action in spec.action_items:
        declaration = action.row_context
        if declaration is None or declaration.dimension is None or not declaration.requires_order:
            continue
        dataset = spec.get_row_context_dataset(key)
        if dataset is not None and declaration.dimension not in dataset.order_references:
            raise ValueError(f"Action {action.id} context dimension must occur in dataset order")
