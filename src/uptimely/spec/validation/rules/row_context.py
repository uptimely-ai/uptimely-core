"""Atomic row-context checks against the selected input profile."""

from __future__ import annotations

import logging

from uptimely.spec import model as spec_model
from uptimely.spec import row_context as row_context_model
from uptimely.spec import selectors

logger = logging.getLogger(__name__)


def validate_row_context_profile_order(spec: spec_model.Spec) -> None:
    """Require profile order for directional row context."""
    logger.debug("    - checking directional row context has profile order")
    for key, operator in spec.operator_items:
        declaration = operator.row_context
        if declaration is None or not declaration.requires_order:
            continue
        profile = spec.get_row_context_profile(key)
        if profile is not None and not profile.order:
            raise ValueError(
                f"Operator {operator.id} directional row context requires profile order"
            )


def validate_dimension(spec: spec_model.Spec) -> None:
    """Require the context dimension to belong to the input profile."""
    logger.debug("    - checking row-context dimensions belong to the input profile")
    for key, operator in spec.operator_items:
        declaration = operator.row_context
        if declaration is None or declaration.dimension is None:
            continue
        dimensions = spec.get_row_context_dimensions(key)
        dimension_id = declaration.dimension.removeprefix(selectors.DIMENSION_PREFIX)
        if dimensions is not None and dimension_id not in dimensions:
            raise ValueError(
                f"Operator {operator.id} context dimension is not in the input profile: "
                f"{dimension_id}"
            )


def validate_dimension_type(spec: spec_model.Spec) -> None:
    """Require the context dimension type to match the requested measure."""
    logger.debug("    - checking row-context dimension types match requested measures")
    for key, operator in spec.operator_items:
        declaration = operator.row_context
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
        resolution = spec.get_row_context_resolution(key, dimension_id)
        if (
            expected_type is not None
            and resolution is not None
            and resolution.type != expected_type
        ):
            raise ValueError(
                f"Operator {operator.id} context dimension resolution must have type "
                f"{expected_type}"
            )


def validate_dimension_order(spec: spec_model.Spec) -> None:
    """Require a directional context dimension to occur in profile order."""
    logger.debug("    - checking directional row-context dimensions occur in profile order")
    for key, operator in spec.operator_items:
        declaration = operator.row_context
        if declaration is None or declaration.dimension is None or not declaration.requires_order:
            continue
        profile = spec.get_row_context_profile(key)
        if profile is not None and declaration.dimension not in profile.order_references:
            raise ValueError(
                f"Operator {operator.id} context dimension must occur in profile order"
            )
