"""Function definition, binding, and operation-contract validation.

Function traversal lives here; ordered semantic phases are coordinated by
:mod:`uptimely.spec.validation.spec`.
"""

from __future__ import annotations

import typing

from uptimely import contracts
from uptimely.spec import model as spec_model

from . import context as context_module
from . import errors


def _validate_binding_selectors(
    value: typing.Any, argument_type: str, path: tuple[str | int, ...]
) -> None:
    """Validate selector types throughout one nested binding value."""
    if isinstance(value, list):
        element_type = argument_type[6:-1] if argument_type.startswith("array[") else "string"
        for item in value:
            _validate_binding_selectors(item, element_type, path)
    elif isinstance(value, dict):
        value_type = argument_type[12:-1] if argument_type.startswith("object{str: ") else "string"
        for item in value.values():
            _validate_binding_selectors(item, value_type, path)
    else:
        _validate_selector_compatibility(value, argument_type, path=path)


def validate_bindings(
    validation_context: context_module.SpecValidationContext,
) -> None:
    """Validate mapping argument names and selector types."""
    for location in validation_context.iter_mappings():
        mapping = location.mapping
        function = validation_context.model.functions.get(mapping.binding.function)
        if function is None:
            continue
        path = (*location.declaration_path, "binding", "args")
        _validate_binding_argument_names(mapping.binding, function, path=path)
        for name, value in mapping.binding.args.items():
            _validate_binding_selectors(value, function.args[name].type, path)


def validate_contracts(validation_context: context_module.SpecValidationContext) -> None:
    """Validate return and dataframe-input contracts for every function."""
    for function_id, function in validation_context.model.functions.root.items():
        path = ("functions", function_id)
        expected_returns = contracts.OPERATION_RETURN_KINDS[function.operation]
        _validate_return_kind(
            function.operation,
            function.returns,
            expected_returns,
            path=(*path, "returns"),
        )
        actual_inputs = sum(argument.type == "dataframe" for argument in function.args.values())
        expected_inputs = contracts.DATAFRAME_INPUT_COUNTS[function.operation]
        _validate_dataframe_argument_count(
            function.operation, expected_inputs, actual_inputs, path=(*path, "args")
        )


def _validate_return_kind(
    operation: contracts.FunctionOperation,
    actual_returns: contracts.FunctionReturns,
    expected_returns: contracts.FunctionReturns,
    *,
    path: tuple[str | int, ...],
) -> None:
    """Require a function's return kind to match its operation."""
    if actual_returns != expected_returns:
        raise errors.SpecError(
            f"Operation {operation} must declare returns={expected_returns}",
            code="invalid_function_return_contract",
            path=path,
        )


def _validate_dataframe_argument_count(
    operation: contracts.FunctionOperation,
    expected_count: int,
    actual_count: int,
    *,
    path: tuple[str | int, ...],
) -> None:
    """Require the operation's expected number of dataframe arguments."""
    if actual_count != expected_count:
        raise errors.SpecError(
            f"Operation {operation} requires {expected_count} dataframe "
            f"argument(s), got {actual_count}",
            code="invalid_function_input_contract",
            path=path,
        )


def _validate_binding_argument_names(
    binding: spec_model.Binding,
    function: spec_model.FunctionTemplate,
    *,
    path: tuple[str | int, ...],
) -> None:
    """Require bound argument names to match the function template contract."""
    declared = set(function.args)
    supplied = set(binding.args)
    missing = sorted(declared - supplied)
    unknown = sorted(supplied - declared)
    if missing or unknown:
        details = []
        if missing:
            details.append("missing arguments: " + ", ".join(missing))
        if unknown:
            details.append("unknown arguments: " + ", ".join(unknown))
        raise errors.SpecError(
            f"Binding for function {binding.function} has " + "; ".join(details),
            code="invalid_binding_arguments",
            path=path,
        )


def _validate_selector_compatibility(
    value: object,
    argument_type: str,
    *,
    path: tuple[str | int, ...],
) -> None:
    """Require one structural selector to match its argument type."""
    if not isinstance(value, str) or not value.startswith("$"):
        return

    if value.startswith(contracts.DATASET_PREFIX) and value.endswith(contracts.DATAFRAME_SELECTOR):
        expected = "dataframe"
    elif value.endswith(contracts.ID_SELECTOR):
        expected = "string"
    else:
        return

    if argument_type != expected:
        raise errors.SpecError(
            f"Reference {value} requires argument type {expected}, got {argument_type}",
            code="invalid_binding_reference_type",
            path=path,
        )
