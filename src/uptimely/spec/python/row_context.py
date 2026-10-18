"""Annotate bound values with observation requirements, not function types."""

from __future__ import annotations

import dataclasses
import typing

from uptimely import row_context

from . import ref

__all__ = [
    "UNBOUNDED",
    "RowContext",
    "ContextExtent",
    "RowContextBinding",
    "time",
    "steps",
    "rows",
    "current",
    "dataset",
]

UNBOUNDED = row_context.UNBOUNDED
RowContext = row_context.RowContext
ContextExtent = row_context.ContextExtent


@dataclasses.dataclass(frozen=True)
class RowContextBinding[T]:
    """A function argument preserved unchanged alongside its row context."""

    value: T
    row_context: row_context.RowContext


def time[T](
    value: T, *, dimension: ref.Reference | str, before: str = "0s", after: str = "0s"
) -> RowContextBinding[T]:
    """Bind a value with preceding/following fixed-time requirements.

    Args:
        value: The original argument, without conversion to a duration.
        dimension: Datetime dimension along which the window is measured.
        before: Required preceding duration, or ``UNBOUNDED``.
        after: Required following duration, or ``UNBOUNDED``.

    Returns:
        A binding annotation that is unwrapped during Spec conversion.

    Raises:
        ValueError: If an extent is not a supported fixed duration.
    """
    return RowContextBinding(
        value,
        row_context.RowContext(
            dimension=dimension.to_model() if isinstance(dimension, ref.Reference) else dimension,
            before=row_context.ContextExtent(time=before),
            after=row_context.ContextExtent(time=after),
        ),
    )


def steps[T](
    value: T,
    *,
    dimension: ref.Reference | str,
    before: row_context.CountExtent = 0,
    after: row_context.CountExtent = 0,
) -> RowContextBinding[T]:
    """Bind a value with integer-coordinate distances, not observation counts.

    Args:
        value: The unchanged function argument.
        dimension: Integer dimension along which distance is measured.
        before: Preceding coordinate distance, or ``UNBOUNDED``.
        after: Following coordinate distance, or ``UNBOUNDED``.

    Returns:
        The argument annotated with its context requirements.

    Raises:
        ValueError: If a bound is not a nonnegative integer or ``UNBOUNDED``.
    """
    return RowContextBinding(
        value,
        row_context.RowContext(
            dimension=dimension.to_model() if isinstance(dimension, ref.Reference) else dimension,
            before=row_context.ContextExtent(steps=before),
            after=row_context.ContextExtent(steps=after),
        ),
    )


def rows[T](
    value: T,
    *,
    before: row_context.CountExtent = 0,
    after: row_context.CountExtent = 0,
) -> RowContextBinding[T]:
    """Bind a value with ordered observation-count requirements.

    Args:
        value: The unchanged function argument.
        before: Preceding observation count, or ``UNBOUNDED``.
        after: Following observation count, or ``UNBOUNDED``.

    Returns:
        The argument annotated with its context requirements.

    Raises:
        ValueError: If a bound is not a nonnegative integer or ``UNBOUNDED``.
    """
    return RowContextBinding(
        value,
        row_context.RowContext(
            before=row_context.ContextExtent(rows=before),
            after=row_context.ContextExtent(rows=after),
        ),
    )


def current() -> row_context.RowContext:
    """Declare that only the current observation is required."""
    return row_context.RowContext()


def dataset() -> RowContext:
    """Declare that the entire input dataset is required."""
    return row_context.RowContext(before=UNBOUNDED, after=UNBOUNDED)


def _context(
    value: typing.Any, explicit: RowContext | RowContextBinding[typing.Any] | None = None
) -> RowContext | None:
    """Consolidate argument annotations and explicit mapping metadata."""
    annotated = _collect(value)
    if explicit is None:
        return annotated
    context = (
        _collect(explicit)
        if isinstance(explicit, RowContextBinding)
        else RowContext.model_validate(explicit)
    )
    return context.merge(annotated) if annotated is not None else context


def _collect(value: typing.Any) -> RowContext | None:
    """Collect annotations recursively within one binding's arguments."""
    context = None
    if isinstance(value, RowContextBinding):
        context = value.row_context
        nested = _collect(value.value)
        return context.merge(nested) if nested is not None else context
    if isinstance(value, dict):
        children = value.values()
    elif isinstance(value, (list, tuple)):
        children = value
    else:
        return None
    for child in children:
        nested = _collect(child)
        if nested is not None:
            context = context.merge(nested) if context is not None else nested
    return context
