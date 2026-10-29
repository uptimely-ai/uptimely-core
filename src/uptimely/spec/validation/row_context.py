"""Atomic row-context checks against the selected input dataset."""

from __future__ import annotations

import dataclasses
import typing

from uptimely import row_context as row_context_model
from uptimely.spec import functions, selectors
from uptimely.spec import model as spec_model

from . import collapse_inputs, traversal


@dataclasses.dataclass(frozen=True)
class RowContext:
    """The row-context declaration and its selected input resource."""

    action: traversal.ActionFacts
    source: traversal.DatasetLocation | None
    model: spec_model.Spec


def iter_row_contexts(spec: spec_model.Spec) -> typing.Iterator[RowContext]:
    """Yield row-context declarations with their selected input dataset."""
    collapse_sources = collapse_inputs.source_index(collapse_inputs.iter_collapse_inputs(spec))
    for action in traversal.iter_actions(spec):
        declaration = action.location.action.row_context
        if declaration is not None:
            source = (
                collapse_sources.get(action.location.key)
                if action.kind == functions.COLLAPSE
                else action.location.dataset_location
            )
            yield RowContext(action, source, spec)


def validate_dataset_order(spec: spec_model.Spec) -> None:
    """Require dataset order for directional row context."""
    for item in iter_row_contexts(spec):
        declaration = item.action.location.action.row_context
        if (
            declaration is not None
            and item.source is not None
            and declaration.requires_order
            and (not item.source.dataset.order)
        ):
            raise ValueError(
                f"Action {item.action.location.action.id} directional row context "
                "requires dataset order"
            )


def validate_dimension(spec: spec_model.Spec) -> None:
    """Require the context dimension to belong to the input entity."""
    for item in iter_row_contexts(spec):
        declaration = item.action.location.action.row_context
        if declaration is None or item.source is None or declaration.dimension is None:
            continue
        dimension_id = declaration.dimension.removeprefix(selectors.DIMENSION_PREFIX)
        if dimension_id not in item.source.dimensions:
            raise ValueError(
                f"Action {item.action.location.action.id} context dimension "
                f"is not in the input entity: {dimension_id}"
            )


def validate_dimension_type(spec: spec_model.Spec) -> None:
    """Require the context dimension type to match the requested measure."""
    for item in iter_row_contexts(spec):
        declaration = item.action.location.action.row_context
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
        dimension = item.model.dimensions.get(dimension_id)
        if (
            expected_type is not None
            and dimension is not None
            and (dimension.type != expected_type)
        ):
            raise ValueError(
                f"Action {item.action.location.action.id} context dimension must have type "
                f"{expected_type}"
            )


def validate_dimension_order(spec: spec_model.Spec) -> None:
    """Require a directional context dimension to occur in dataset order."""
    for item in iter_row_contexts(spec):
        declaration = item.action.location.action.row_context
        if (
            declaration is not None
            and item.source is not None
            and (declaration.dimension is not None)
            and declaration.requires_order
            and (declaration.dimension not in {key.dimension for key in item.source.dataset.order})
        ):
            raise ValueError(
                f"Action {item.action.location.action.id} context dimension must occur "
                "in dataset order"
            )
