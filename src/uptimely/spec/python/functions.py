"""Optional semantic contracts for Python function implementations."""

from __future__ import annotations

import typing
from collections import abc

from uptimely.spec import functions as function_kinds

__all__ = ["function"]

_KIND_ATTRIBUTE = "__uptimely_kind__"
_Parameters = typing.ParamSpec("_Parameters")
_Result = typing.TypeVar("_Result")


def function(
    *,
    kind: function_kinds.FunctionKindId,
) -> abc.Callable[
    [abc.Callable[_Parameters, _Result]],
    abc.Callable[_Parameters, _Result],
]:
    """Declare optional function semantics without wrapping the implementation.

    Args:
        kind: Execution contract used to validate uses of this function.

    Returns:
        A decorator that attaches metadata and returns the original callable.

    Raises:
        ValueError: If the kind is unsupported or conflicts with existing metadata.
    """
    if kind not in function_kinds.FUNCTION_KINDS:
        raise ValueError(f"Unsupported function kind: {kind}")

    def decorate(
        implementation: abc.Callable[_Parameters, _Result],
    ) -> abc.Callable[_Parameters, _Result]:
        existing = declared_kind(implementation)
        if existing is not None and existing != kind:
            raise ValueError(f"Function kind '{kind}' conflicts with decorated kind '{existing}'")
        setattr(implementation, _KIND_ATTRIBUTE, kind)
        return implementation

    return decorate


def declared_kind(
    implementation: abc.Callable[..., object],
) -> function_kinds.FunctionKindId | None:
    """Read declared semantics without inferring them from a signature."""
    value = getattr(implementation, _KIND_ATTRIBUTE, None)
    if value is None:
        return None
    if value not in function_kinds.FUNCTION_KINDS:
        raise ValueError(f"Unsupported function kind: {value}")
    return typing.cast(function_kinds.FunctionKindId, value)
