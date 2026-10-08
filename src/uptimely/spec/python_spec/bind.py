"""Python-friendly function bindings."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .ref import Reference

__all__ = [
    "Bind",
    "bind",
]


@dataclass(frozen=True)
class Bind:
    """A callable and its Python-friendly argument bindings."""

    function: Callable[..., object]
    args: dict[str, Any]
    function_id: str | None = None


def bind(function: Callable[..., object], /, function_id: str | None = None, **args: Any) -> Bind:
    """Bind named arguments to a plain vectorize function."""
    return Bind(function=function, args=args, function_id=function_id)


def _entrypoint(function: Callable[..., object]) -> str:
    """Return the importable entrypoint for a declared Python function."""
    return f"{function.__module__}:{function.__name__}"


def _binding_value(value: Any) -> Any:
    """Convert Python references recursively to canonical binding values."""
    from .feature import Aggregation

    if isinstance(value, Reference):
        return value.to_model()
    if isinstance(value, Aggregation):
        return {
            "function": value.id,
            "args": {name: _binding_value(argument) for name, argument in value.args.items()},
        }
    if isinstance(value, list):
        return [_binding_value(item) for item in value]
    if isinstance(value, tuple):
        return [_binding_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _binding_value(item) for key, item in value.items()}
    return value


def _argument_definition(value: Any) -> dict[str, Any]:
    """Infer a recursive function-argument schema from a bound value."""
    from .feature import Aggregation

    if isinstance(value, Reference):
        return {"type": "dataframe" if value.type in {"dataset", "fragment"} else "string"}
    if isinstance(value, Aggregation):
        return {"type": "aggregation"}
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


def _operation_id(bind: Bind, identifier: str | None) -> str:
    """Return the explicit or callable-derived identifier for an operation."""
    return identifier or bind.function_id or bind.function.__name__


def _binding_args(bind: Bind) -> dict[str, Any]:
    """Convert a Python binding's arguments to canonical binding values."""
    return {name: _binding_value(value) for name, value in bind.args.items()}


def _models_by_id(declarations: list[Any]) -> dict[str, Any]:
    """Convert declarations once and return their canonical models keyed by ID."""
    models = [declaration.to_model() for declaration in declarations]
    return {model.id: model for model in models}
