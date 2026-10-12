"""Python-friendly dataset feature declarations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from uptimely.spec.json_spec import json_model

from .bind import Bind
from .row_context import RowContext, RowContextBinding, _context

__all__ = [
    "Feature",
    "Vectorize",
    "Aggregation",
    "aggregation",
]


@dataclass(frozen=True)
class Aggregation:
    """An aggregate function binding evaluated within a collapse operation."""

    function: Callable[..., object]
    args: dict[str, Any]
    function_id: str | None = None

    @property
    def id(self) -> str:
        """Return the explicit or callable-derived function identifier."""
        return self.function_id or self.function.__name__


def aggregation(
    function: Callable[..., object],
    /,
    function_id: str | None = None,
    **args: Any,
) -> Aggregation:
    """Bind an aggregate function within a collapse operation.

    Args:
        function: The aggregate callable.
        function_id: Optional catalog identifier.
        **args: Function arguments.

    Returns:
        A per-feature aggregation binding.

    """
    return Aggregation(
        function=function,
        args=args,
        function_id=function_id,
    )


@dataclass(frozen=True)
class Feature:
    """Metadata for a dataset feature, independent of how it is produced."""

    id: str
    description: str | None = None
    type: str | None = None
    unit: str | None = None

    def to_model(self) -> json_model.Feature:
        """Convert this feature declaration to its JSON model."""
        return json_model.Feature(
            id=self.id,
            description=self.description,
            type=self.type,
            unit=self.unit,
        )


@dataclass(frozen=True)
class Vectorize:
    """A vectorized dataset feature."""

    id: str
    bind: Bind
    description: str | None = None
    unit: str | None = None
    row_context: RowContext | RowContextBinding[Any] | None = None

    def __post_init__(self) -> None:
        """Consolidate requirements on the calculated feature, not its binding."""
        object.__setattr__(self, "row_context", _context(self.bind.args, self.row_context))

    def to_model(self) -> json_model.Feature:
        """Convert this vectorized feature metadata to its JSON model."""
        return json_model.Feature(
            id=self.id,
            description=self.description,
            unit=self.unit,
            row_context=_context(None, self.row_context),
        )
