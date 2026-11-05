"""Convert Python binding declarations into document values and argument schemas."""

from __future__ import annotations

import typing

from uptimely.spec import arg_types

from . import bind, references, row_context
from . import dimension as dimension_module
from . import feature as feature_module
from . import profile as profile_module


def resource_reference(value: object) -> references.Reference | references.Params | None:
    """Normalize declaration instances and deferred lookups at one boundary."""
    if isinstance(value, (references.Reference, references.Params)):
        return value
    if isinstance(value, feature_module.Feature):
        return references.FeatureReference(kind="feature", value=f"$features.{value.id}")
    if isinstance(value, dimension_module.Dimension):
        return references.DimensionReference(kind=arg_types.STRING, value=f"$dimensions.{value.id}")
    if isinstance(value, dimension_module.Resolution):
        return references.Reference(kind=arg_types.STRING, value=value.id)
    if isinstance(value, profile_module.Profile):
        return references.ProfileReference(kind=arg_types.STRING, value=f"$profiles.{value.id}")
    return None


def to_value(value: typing.Any) -> typing.Any:
    """Convert Python references and nested bindings to document values."""
    if isinstance(value, row_context.RowContextBinding):
        return to_value(value.value)
    reference = resource_reference(value)
    if reference is not None:
        return reference.to_model()
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
    reference = resource_reference(value)
    if reference is not None:
        if isinstance(reference, references.Reference) and reference.kind in {
            arg_types.DATAFRAME,
            arg_types.array_of(arg_types.STRING),
        }:
            return {"type": reference.kind}
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
