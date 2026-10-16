"""Python-friendly function bindings."""

from __future__ import annotations

import dataclasses
import typing

from . import ref, row_context

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


def _entrypoint(function: ref.FunctionReference) -> str:
    """Return the entrypoint for a declared function reference."""
    return function.entrypoint


def _binding_value(value: typing.Any) -> typing.Any:
    """Convert Python references recursively to canonical binding values."""
    if isinstance(value, row_context.RowContextBinding):
        return _binding_value(value.value)
    if isinstance(value, ref.Reference):
        return value.to_model()
    if isinstance(value, Bind):
        return {
            "function": _function_id(value),
            "args": {name: _binding_value(argument) for name, argument in value.args.items()},
        }
    if isinstance(value, list):
        return [_binding_value(item) for item in value]
    if isinstance(value, tuple):
        return [_binding_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _binding_value(item) for key, item in value.items()}
    return value


def _argument_definition(value: typing.Any) -> dict[str, typing.Any]:
    """Infer a recursive function-argument schema from a bound value."""
    if isinstance(value, row_context.RowContextBinding):
        return _argument_definition(value.value)
    if isinstance(value, ref.Reference):
        return {"type": "dataframe" if value.type == "dataset" else "string"}
    if isinstance(value, (list, tuple)):
        item_definitions = [_argument_definition(item) for item in value]
        if item_definitions and all(item == item_definitions[0] for item in item_definitions[1:]):
            return {"type": f"array[{item_definitions[0]['type']}]"}
        return {"type": "array"}
    if isinstance(value, dict):
        if value and all(isinstance(key, str) for key in value):
            value_definitions = [_argument_definition(item) for item in value.values()]
            if value_definitions and all(
                item == value_definitions[0] for item in value_definitions[1:]
            ):
                return {"type": f"object{{str: {value_definitions[0]['type']}}}"}
        return {"type": "object"}
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int):
        return {"type": "integer"}
    if isinstance(value, float):
        return {"type": "float"}
    if isinstance(value, str):
        return {"type": "string"}
    return {"type": "object"}


def _function_id(bind: Bind) -> str:
    """Return the explicit or reference-derived function identifier."""
    return bind.function_id or bind.function.name


def _mapping_id(bind: Bind, identifier: str | None) -> str:
    """Return the explicit mapping identifier or default it to the function identifier."""
    return identifier or _function_id(bind)


def _binding_args(bind: Bind) -> dict[str, typing.Any]:
    """Convert a Python binding's arguments to canonical binding values."""
    return {name: _binding_value(value) for name, value in bind.args.items()}
