"""Optional semantic contracts for Python function implementations."""

from __future__ import annotations

import typing
from collections import abc

from uptimely.spec import function_kinds

__all__ = ["function"]

_KIND_ATTRIBUTE = "__uptimely_kind__"
_CATEGORY_ATTRIBUTE = "__uptimely_category__"
_Parameters = typing.ParamSpec("_Parameters")
_Result = typing.TypeVar("_Result")


def function(
    *,
    kind: function_kinds.FunctionKindId,
    category: str | None = None,
) -> abc.Callable[
    [abc.Callable[_Parameters, _Result]],
    abc.Callable[_Parameters, _Result],
]:
    """Declare function metadata without wrapping the implementation.

    Args:
        kind: Execution contract used to validate uses of this function.
        category: Optional free-form category stored with the function in the Spec.

    Returns:
        A decorator that attaches metadata and returns the original callable.

    Raises:
        TypeError: If category is not a string.
        ValueError: If the kind is unsupported or metadata conflicts with existing values.
    """
    if kind not in function_kinds.FUNCTION_KINDS:
        raise ValueError(f"Unsupported function kind: {kind}")
    if category is not None and not isinstance(category, str):
        raise TypeError("Function category must be a string")

    def decorate(
        implementation: abc.Callable[_Parameters, _Result],
    ) -> abc.Callable[_Parameters, _Result]:
        existing = declared_kind(implementation)
        if existing is not None and existing != kind:
            raise ValueError(f"Function kind '{kind}' conflicts with decorated kind '{existing}'")
        existing_category = declared_category(implementation)
        if existing_category is not None and category is not None and existing_category != category:
            raise ValueError(
                f"Function category '{category}' conflicts with decorated category "
                f"'{existing_category}'"
            )
        setattr(implementation, _KIND_ATTRIBUTE, kind)
        if category is not None:
            setattr(implementation, _CATEGORY_ATTRIBUTE, category)
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


def declared_category(implementation: abc.Callable[..., object]) -> str | None:
    """Return the optional category declared on a callable."""
    value = getattr(implementation, _CATEGORY_ATTRIBUTE, None)
    if value is not None and not isinstance(value, str):
        raise ValueError(f"Unsupported function category: {value!r}")
    return value
