"""Reusable Python function metadata without operator classifications."""

from __future__ import annotations

import dataclasses
import typing
from collections import abc

from uptimely.spec import function_contracts

__all__ = ["function"]
_METADATA_ATTRIBUTE = "__uptimely_contract__"
_Parameters = typing.ParamSpec("_Parameters")
_Result = typing.TypeVar("_Result")


@dataclasses.dataclass(frozen=True)
class Metadata:
    """Explicit reusable contracts and descriptive metadata for a callable."""

    returns: function_contracts.ReturnRole | None = None
    args: dict[str, str] | None = None
    category: str | None = None
    validate_signature: bool = True


def declared_metadata(implementation: abc.Callable[..., object]) -> Metadata:
    """Read callable metadata without interpreting operator behavior."""
    value = getattr(implementation, _METADATA_ATTRIBUTE, None)
    if value is None:
        return Metadata()
    if not isinstance(value, Metadata):
        raise TypeError("Invalid function contract metadata")
    return value


def function(
    *,
    returns: function_contracts.ReturnRole | None = None,
    args: dict[str, str] | None = None,
    category: str | None = None,
    validate_signature: bool = True,
) -> abc.Callable[
    [abc.Callable[_Parameters, _Result]],
    abc.Callable[_Parameters, _Result],
]:
    """Declare reusable contracts without wrapping the callable.

    Args:
        returns: Independent return role; otherwise inferred from an unambiguous
            dataframe or None return annotation when the function is referenced.
        args: Explicit argument types, required when signature inspection is disabled.
        category: Optional descriptive grouping label, never an execution policy.
        validate_signature: Whether authoring and compilation inspect the signature.

    Returns:
        A decorator returning the original callable unchanged.

    Raises:
        TypeError: Metadata has an invalid type.
        ValueError: Contracts are missing or conflict with existing metadata.
    """
    function_contracts.validate_metadata(returns, args)
    if category is not None and not isinstance(category, str):
        raise TypeError("Function category must be a string")
    if not isinstance(validate_signature, bool):
        raise TypeError("validate_signature must be a boolean")
    if not validate_signature and (returns is None or args is None):
        raise ValueError("Disabling signature inspection requires explicit args and returns")
    metadata = Metadata(
        returns, args.copy() if args is not None else None, category, validate_signature
    )

    def decorate(
        implementation: abc.Callable[_Parameters, _Result],
    ) -> abc.Callable[_Parameters, _Result]:
        existing = getattr(implementation, _METADATA_ATTRIBUTE, None)
        if existing is not None and existing != metadata:
            raise ValueError("Function contract conflicts with decorated metadata")
        setattr(implementation, _METADATA_ATTRIBUTE, metadata)
        return implementation

    return decorate
