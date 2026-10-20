"""Atomic argument-name and selector-type checks."""

from __future__ import annotations

from uptimely import contracts

from . import context as context_module
from . import errors


def validate_arguments(item: context_module.MappingFacts) -> context_module.ValidationResult:
    """Require the supplied argument names to match the function signature."""
    if item.function is None:
        return None
    supplied = item.location.mapping.binding.args
    missing = item.function.args.keys() - supplied.keys()
    unknown = supplied.keys() - item.function.args.keys()
    if missing or unknown:
        details = (["missing arguments: " + ", ".join(sorted(missing))] if missing else []) + (
            ["unknown arguments: " + ", ".join(sorted(unknown))] if unknown else []
        )
        return errors.SpecError(
            f"Binding for function {item.location.mapping.binding.function} has "
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
    if value.startswith(contracts.DATASET_PREFIX) and value.endswith(contracts.DATAFRAME_SELECTOR):
        expected = "dataframe"
    elif value.endswith(contracts.ID_SELECTOR):
        expected = "string"
    else:
        return None
    if argument_type != expected:
        return errors.SpecError(
            f"Reference {value} requires argument type {expected}, got {argument_type}",
            code="invalid_binding_reference_type",
            path=path,
        )
    return None
