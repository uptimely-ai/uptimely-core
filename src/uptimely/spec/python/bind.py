"""Python-friendly function bindings."""

from __future__ import annotations

import dataclasses
import typing

from . import ref

__all__ = [
    "Bind",
    "bind",
]


@dataclasses.dataclass(frozen=True)
class Bind:
    """A function reference and its Python-friendly argument bindings."""

    function: ref.FunctionReference
    args: dict[str, typing.Any]
    function_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.function, ref.FunctionReference):
            raise TypeError(
                "Bind.function must be a reference created with "
                "ref.function(callable_or_entrypoint)"
            )


def bind(
    function: ref.FunctionReference,
    /,
    function_id: str | None = None,
    **args: typing.Any,
) -> Bind:
    """Bind named arguments to a function reference.

    Args:
        function: A reference created with ``ref.function(callable_or_entrypoint)``.
        function_id: Optional catalog identifier.
        **args: Actual function arguments, optionally annotated with row context.

    Returns:
        A declaration preserving primitive arguments and separate metadata.

    Raises:
        TypeError: If function is not a reference created with ``ref.function``.
    """
    return Bind(function=function, args=args, function_id=function_id)
