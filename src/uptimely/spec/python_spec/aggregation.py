"""Python declarations for aggregate function bindings."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

__all__ = ["Aggregation", "aggregation"]


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
    return Aggregation(function=function, args=args, function_id=function_id)
