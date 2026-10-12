"""Annotate bound values with observation requirements, not function types."""

from dataclasses import dataclass
from typing import Any

from uptimely.row_context import UNBOUNDED, ContextExtent, CountExtent, RowContext

__all__ = [
    "UNBOUNDED",
    "RowContext",
    "ContextExtent",
    "RowContextBinding",
    "time",
    "steps",
    "rows",
    "current",
    "partition",
    "dataset",
]


@dataclass(frozen=True)
class RowContextBinding[T]:
    """A function argument preserved unchanged alongside its row context."""

    value: T
    row_context: RowContext


def time[T](value: T, *, before: str = "0s", after: str = "0s") -> RowContextBinding[T]:
    """Bind a value with preceding/following fixed-time requirements.

    Args:
        value: The original argument, without conversion to a duration.
        before: Required preceding duration, or ``UNBOUNDED``.
        after: Required following duration, or ``UNBOUNDED``.

    Returns:
        A binding annotation that is unwrapped during specification conversion.

    Raises:
        ValueError: If an extent is not a supported fixed duration.
    """
    return RowContextBinding(
        value,
        RowContext(before=ContextExtent(time=before), after=ContextExtent(time=after)),
    )


def steps[T](value: T, *, before: CountExtent = 0, after: CountExtent = 0) -> RowContextBinding[T]:
    """Bind a value with integer-coordinate distances, not observation counts.

    Args:
        value: The unchanged function argument.
        before: Preceding coordinate distance, or ``UNBOUNDED``.
        after: Following coordinate distance, or ``UNBOUNDED``.

    Returns:
        The argument annotated with its context requirements.

    Raises:
        ValueError: If a bound is not a nonnegative integer or ``UNBOUNDED``.
    """
    return RowContextBinding(
        value,
        RowContext(before=ContextExtent(steps=before), after=ContextExtent(steps=after)),
    )


def rows[T](value: T, *, before: CountExtent = 0, after: CountExtent = 0) -> RowContextBinding[T]:
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
        RowContext(before=ContextExtent(rows=before), after=ContextExtent(rows=after)),
    )


def current() -> RowContext:
    """Declare that only the current observation is required."""
    return RowContext()


def partition() -> RowContext:
    """Declare that the entire input partition is required."""
    return RowContext(extent="partition")


def dataset() -> RowContext:
    """Declare that the entire input dataset is required."""
    return RowContext(extent="dataset")


def _context(
    value: Any, explicit: RowContext | RowContextBinding[Any] | None = None
) -> RowContext | None:
    """Consolidate argument annotations and explicit feature/operation metadata."""
    annotated = _collect(value)
    if explicit is None:
        return annotated
    context = (
        _collect(explicit)
        if isinstance(explicit, RowContextBinding)
        else RowContext.model_validate(explicit)
    )
    return context.merge(annotated) if annotated is not None else context


def _collect(value: Any) -> RowContext | None:
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
