"""Atomic argument-name and selector-type checks."""

from __future__ import annotations

import collections.abc

from uptimely.spec import arg_types, selectors
from uptimely.spec import model as spec_model
from uptimely.spec.validation import errors

from . import actions as action_rules


def _iter_binding_selectors(
    value: object, argument_type: str
) -> collections.abc.Iterator[tuple[object, str]]:
    """Flatten nested binding values with their inherited argument types."""
    if isinstance(value, list):
        element_type = arg_types.array_item_type(argument_type) or arg_types.STRING
        for item in value:
            yield from _iter_binding_selectors(item, element_type)
    elif isinstance(value, dict):
        value_type = arg_types.object_value_type(argument_type) or arg_types.STRING
        for item in value.values():
            yield from _iter_binding_selectors(item, value_type)
    else:
        yield (value, argument_type)


def iter_binding_selectors(
    spec: spec_model.Spec,
) -> collections.abc.Iterator[tuple[errors.SpecPath, object, str]]:
    """Yield supplied selector values paired with their declared argument types."""
    for item in action_rules.iter_actions(spec):
        if item.function is None:
            continue
        path = (*item.declaration_path, "binding", "args")
        for name, value in item.action.binding.args.items():
            argument = item.function.args.get(name)
            if argument is not None:
                for selector, argument_type in _iter_binding_selectors(value, argument.type):
                    yield path, selector, argument_type


def validate_arguments(spec: spec_model.Spec) -> None:
    """Require the supplied argument names to match the function signature."""
    for item in action_rules.iter_actions(spec):
        if item.function is None:
            continue
        supplied = item.action.binding.args
        missing = item.function.args.keys() - supplied.keys()
        unknown = supplied.keys() - item.function.args.keys()
        if missing or unknown:
            details = (["missing arguments: " + ", ".join(sorted(missing))] if missing else []) + (
                ["unknown arguments: " + ", ".join(sorted(unknown))] if unknown else []
            )
            raise errors.SpecError(
                f"Binding for function {item.action.binding.function} has " + "; ".join(details),
                code="invalid_binding_arguments",
                path=(*item.declaration_path, "binding", "args"),
            )


def validate_selector_type(spec: spec_model.Spec) -> None:
    """Require a structural selector's argument type to match its value kind."""
    for path, value, argument_type in iter_binding_selectors(spec):
        if not isinstance(value, str) or not value.startswith("$"):
            continue
        if value.startswith(selectors.DATASET_PREFIX) and value.endswith(
            selectors.DATAFRAME_SELECTOR
        ):
            expected = arg_types.DATAFRAME
        elif value.startswith(selectors.DATASET_PREFIX) and value.endswith(
            selectors.DIMENSION_IDS_SELECTOR
        ):
            expected = arg_types.array_of(arg_types.STRING)
        elif value.endswith(selectors.ID_SELECTOR):
            expected = arg_types.STRING
        else:
            continue
        if argument_type != expected:
            raise errors.SpecError(
                f"Reference {value} requires argument type {expected}, got {argument_type}",
                code="invalid_binding_reference_type",
                path=path,
            )
