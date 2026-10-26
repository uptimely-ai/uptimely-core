"""Convert Python binding declarations into document values and argument schemas."""

from __future__ import annotations

import typing

from .. import arg_types
from . import bind, ref, row_context


def to_value(value: typing.Any) -> typing.Any:
    """Convert Python references and nested bindings to document values."""
    if isinstance(value, row_context.RowContextBinding):
        return to_value(value.value)
    if isinstance(value, ref.Reference):
        return value.to_model()
    if isinstance(value, bind.Bind):
        return {
            "function": value.function_id or value.function.name,
            "args": {name: to_value(argument) for name, argument in value.args.items()},
        }
    if isinstance(value, (list, tuple)):
        return [to_value(item) for item in value]
    if isinstance(value, dict):
        return {key: to_value(item) for key, item in value.items()}
    return value


def argument_definition(value: typing.Any) -> dict[str, str]:
    """Infer a recursive function-argument schema from a bound value."""
    if isinstance(value, row_context.RowContextBinding):
        return argument_definition(value.value)
    if isinstance(value, ref.Reference):
        if value.type == "dataset":
            return {"type": arg_types.DATAFRAME}
        if value.type == arg_types.array_of(arg_types.STRING):
            return {"type": value.type}
        return {"type": arg_types.STRING}
    if isinstance(value, (list, tuple)):
        item_definitions = [argument_definition(item) for item in value]
        if item_definitions and all(item == item_definitions[0] for item in item_definitions[1:]):
            return {"type": arg_types.array_of(item_definitions[0]["type"])}
        return {"type": arg_types.ARRAY}
    if isinstance(value, dict):
        if value and all(isinstance(key, str) for key in value):
            value_definitions = [argument_definition(item) for item in value.values()]
            if value_definitions and all(
                item == value_definitions[0] for item in value_definitions[1:]
            ):
                return {"type": arg_types.object_values_of(value_definitions[0]["type"])}
        return {"type": arg_types.OBJECT}
    if isinstance(value, bool):
        return {"type": arg_types.BOOLEAN}
    if isinstance(value, int):
        return {"type": arg_types.INTEGER}
    if isinstance(value, float):
        return {"type": arg_types.FLOAT}
    if isinstance(value, str):
        return {"type": arg_types.STRING}
    return {"type": arg_types.OBJECT}
