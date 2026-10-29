"""Atomic row-context checks against the selected input dataset."""

from __future__ import annotations

import collections.abc

from uptimely import row_context as row_context_model
from uptimely.spec import functions, selectors
from uptimely.spec import model as spec_model

from . import actions as action_rules
from . import datasets as dataset_rules
from .actions import inputs


def iter_row_contexts(
    spec: spec_model.Spec,
) -> collections.abc.Iterator[
    tuple[action_rules.ActionDeclaration, dataset_rules.DatasetDeclaration | None]
]:
    """Yield row-context declarations with their selected input dataset."""
    for item in inputs.iter_input_sources(spec):
        action = item.action
        declaration = action.action.row_context
        if declaration is not None:
            source = (
                item.source if action.kind == functions.COLLAPSE else action.dataset_declaration
            )
            yield action, source


def validate_dataset_order(spec: spec_model.Spec) -> None:
    """Require dataset order for directional row context."""
    for action, source in iter_row_contexts(spec):
        declaration = action.action.row_context
        if (
            declaration is not None
            and source is not None
            and declaration.requires_order
            and not source.dataset.order
        ):
            raise ValueError(
                f"Action {action.action.id} directional row context requires dataset order"
            )


def validate_dimension(spec: spec_model.Spec) -> None:
    """Require the context dimension to belong to the input entity."""
    for action, source in iter_row_contexts(spec):
        declaration = action.action.row_context
        if declaration is None or source is None or declaration.dimension is None:
            continue
        dimension_id = declaration.dimension.removeprefix(selectors.DIMENSION_PREFIX)
        if dimension_id not in source.dimensions:
            raise ValueError(
                f"Action {action.action.id} context dimension "
                f"is not in the input entity: {dimension_id}"
            )


def validate_dimension_type(spec: spec_model.Spec) -> None:
    """Require the context dimension type to match the requested measure."""
    for action, _ in iter_row_contexts(spec):
        declaration = action.action.row_context
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
            raise ValueError(
                f"Action {action.action.id} context dimension must have type {expected_type}"
            )


def validate_dimension_order(spec: spec_model.Spec) -> None:
    """Require a directional context dimension to occur in dataset order."""
    for action, source in iter_row_contexts(spec):
        declaration = action.action.row_context
        if (
            declaration is not None
            and source is not None
            and (declaration.dimension is not None)
            and declaration.requires_order
            and declaration.dimension not in {key.dimension for key in source.dataset.order}
        ):
            raise ValueError(
                f"Action {action.action.id} context dimension must occur in dataset order"
            )
