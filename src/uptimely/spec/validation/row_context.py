"""Atomic row-context checks against the prepared input dataset."""

from __future__ import annotations

import dataclasses
import typing

from uptimely.spec import model as spec_model

from .. import functions, selectors
from . import context as context_module


@dataclasses.dataclass(frozen=True)
class RowContext:
    """The row-context declaration and its selected input resource."""

    action: context_module.ActionFacts
    source: context_module.DatasetLocation | None
    model: spec_model.Spec


def iter_row_contexts(
    actions: typing.Iterable[context_module.ActionFacts],
    model: spec_model.Spec,
    collapse_sources: dict[tuple[str, str, str], context_module.DatasetLocation],
) -> typing.Iterator[tuple[context_module.ActionFacts, RowContext | None]]:
    """Yield each action with row-context facts for its selected input dataset."""
    for action in actions:
        declaration = action.location.action.row_context
        if declaration is None:
            yield action, None
        else:
            source = (
                collapse_sources.get(action.location.key)
                if action.kind == functions.COLLAPSE
                else action.location.dataset_location
            )
            yield action, RowContext(action, source, model)


def validate_dataset_order(item: RowContext) -> context_module.ValidationResult:
    """Require dataset order for directional row context."""
    declaration = item.action.location.action.row_context
    if (
        declaration is not None
        and item.source is not None
        and declaration.requires_order
        and not item.source.dataset.order
    ):
        return ValueError(
            f"Action {item.action.location.action.id} directional row context "
            "requires dataset order"
        )
    return None


def validate_dimension(item: RowContext) -> context_module.ValidationResult:
    """Require the context dimension to belong to the input entity."""
    declaration = item.action.location.action.row_context
    if declaration is None or item.source is None or declaration.dimension is None:
        return None
    dimension_id = declaration.dimension.removeprefix(selectors.DIMENSION_PREFIX)
    if dimension_id not in item.source.dimensions:
        return ValueError(
            f"Action {item.action.location.action.id} context dimension "
            f"is not in the input entity: {dimension_id}"
        )
    return None


def validate_dimension_type(item: RowContext) -> context_module.ValidationResult:
    """Require the context dimension type to match the requested measure."""
    declaration = item.action.location.action.row_context
    if declaration is None or declaration.dimension is None:
        return None
    measures = {
        measure
        for direction in (declaration.before, declaration.after)
        if hasattr(direction, "model_dump")
        for measure in direction.model_dump(exclude_none=True)
    }
    expected_type = ("datetime" if "time" in measures else "integer") if measures else None
    dimension_id = declaration.dimension.removeprefix(selectors.DIMENSION_PREFIX)
    dimension = item.model.dimensions.get(dimension_id)
    if expected_type is not None and dimension is not None and dimension.type != expected_type:
        return ValueError(
            f"Action {item.action.location.action.id} context dimension must have type "
            f"{expected_type}"
        )
    return None


def validate_dimension_order(item: RowContext) -> context_module.ValidationResult:
    """Require a directional context dimension to occur in dataset order."""
    declaration = item.action.location.action.row_context
    if (
        declaration is not None
        and item.source is not None
        and declaration.dimension is not None
        and declaration.requires_order
        and declaration.dimension not in {key.dimension for key in item.source.dataset.order}
    ):
        return ValueError(
            f"Action {item.action.location.action.id} context dimension must occur in dataset order"
        )
    return None
