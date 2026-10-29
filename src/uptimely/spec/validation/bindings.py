"""Atomic argument-name and selector-type checks."""

from __future__ import annotations

import collections.abc

from .. import arg_types, selectors
from . import context as context_module
from . import errors


def iter_bound_actions(
    actions: collections.abc.Iterable[context_module.ActionFacts],
) -> collections.abc.Iterator[context_module.ActionFacts]:
    """Yield actions whose declared function is available for binding checks."""
    return (item for item in actions if item.function is not None)


def _binding_selectors(
    value: object, argument_type: str
) -> collections.abc.Iterator[tuple[object, str]]:
    """Flatten nested binding values with their inherited argument types."""
    if isinstance(value, list):
        element_type = arg_types.array_item_type(argument_type) or arg_types.STRING
        for item in value:
            yield from _binding_selectors(item, element_type)
    elif isinstance(value, dict):
        value_type = arg_types.object_value_type(argument_type) or arg_types.STRING
        for item in value.values():
            yield from _binding_selectors(item, value_type)
    else:
        yield value, argument_type


def iter_binding_selectors(
    item: context_module.ActionFacts,
) -> collections.abc.Iterator[tuple[object, str]]:
    """Yield supplied selector values paired with their declared argument types."""
    if item.function is None:
        return
    for name, value in item.location.action.binding.args.items():
        argument = item.function.args.get(name)
        if argument is not None:
            yield from _binding_selectors(value, argument.type)


def validate_arguments(item: context_module.ActionFacts) -> context_module.ValidationResult:
    """Require the supplied argument names to match the function signature."""
    if item.function is None:
        return None
    supplied = item.location.action.binding.args
    missing = item.function.args.keys() - supplied.keys()
    unknown = supplied.keys() - item.function.args.keys()
    if missing or unknown:
        details = (["missing arguments: " + ", ".join(sorted(missing))] if missing else []) + (
            ["unknown arguments: " + ", ".join(sorted(unknown))] if unknown else []
        )
        return errors.SpecError(
            f"Binding for function {item.location.action.binding.function} has "
            + "; ".join(details),
            code="invalid_binding_arguments",
            path=(*item.location.declaration_path, "binding", "args"),
        )
    return None


def validate_selector_type(
    value: object, argument_type: str, path: context_module.SpecPath
) -> context_module.ValidationResult:
    """Require a structural selector's argument type to match its value kind."""
    if not isinstance(value, str) or not value.startswith("$"):
        return None
    if value.startswith(selectors.DATASET_PREFIX) and value.endswith(selectors.DATAFRAME_SELECTOR):
        expected = arg_types.DATAFRAME
    elif value.startswith(selectors.DATASET_PREFIX) and value.endswith(
        selectors.DIMENSION_IDS_SELECTOR
    ):
        expected = arg_types.array_of(arg_types.STRING)
    elif value.endswith(selectors.ID_SELECTOR):
        expected = arg_types.STRING
    else:
        return None
    if argument_type != expected:
        return errors.SpecError(
            f"Reference {value} requires argument type {expected}, got {argument_type}",
            code="invalid_binding_reference_type",
            path=path,
        )
    return None
