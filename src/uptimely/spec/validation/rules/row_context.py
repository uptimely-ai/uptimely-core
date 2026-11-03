"""Atomic row-context checks against the selected input profile."""

from __future__ import annotations

import logging

from uptimely import row_context as row_context_model
from uptimely.spec import model as spec_model
from uptimely.spec import selectors

logger = logging.getLogger(__name__)


def validate_dataset_order(spec: spec_model.Spec) -> None:
    """Require profile order for directional row context."""
    logger.debug("    - checking directional row context has profile order")
    for key, action in spec.action_items:
        declaration = action.row_context
        if declaration is None or not declaration.requires_order:
            continue
        profile = spec.get_row_context_profile(key)
        if profile is not None and not profile.order:
            raise ValueError(f"Action {action.id} directional row context requires profile order")


def validate_dimension(spec: spec_model.Spec) -> None:
    """Require the context dimension to belong to the input profile."""
    logger.debug("    - checking row-context dimensions belong to the input profile")
    for key, action in spec.action_items:
        declaration = action.row_context
        if declaration is None or declaration.dimension is None:
            continue
        dimensions = spec.get_row_context_dimensions(key)
        dimension_id = declaration.dimension.removeprefix(selectors.DIMENSION_PREFIX)
        if dimensions is not None and dimension_id not in dimensions:
            raise ValueError(
                f"Action {action.id} context dimension is not in the input profile: {dimension_id}"
            )


def validate_dimension_type(spec: spec_model.Spec) -> None:
    """Require the context dimension type to match the requested measure."""
    logger.debug("    - checking row-context dimension types match requested measures")
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
    """Require a directional context dimension to occur in profile order."""
    logger.debug("    - checking directional row-context dimensions occur in profile order")
    for key, action in spec.action_items:
        declaration = action.row_context
        if declaration is None or declaration.dimension is None or not declaration.requires_order:
            continue
        profile = spec.get_row_context_profile(key)
        if profile is not None and declaration.dimension not in profile.order_references:
            raise ValueError(f"Action {action.id} context dimension must occur in profile order")
