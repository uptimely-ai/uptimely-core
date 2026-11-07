"""Compatibility exports for portable row-context requirements."""

from .spec.row_context import (
    UNBOUNDED,
    ContextExtent,
    CountExtent,
    RowContext,
    TimeExtent,
    duration_nanoseconds,
)

__all__ = [
    "UNBOUNDED",
    "ContextExtent",
    "CountExtent",
    "RowContext",
    "TimeExtent",
    "duration_nanoseconds",
]
