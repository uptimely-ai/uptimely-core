"""Function operation and binding contract validation."""

from __future__ import annotations

import typing

from uptimely import contracts

from . import context as context_module
from . import errors

__all__ = [
    "_validate_binding_contract",
    "_validate_binding_contracts",
    "_validate_function_contracts",
    "_validate_operation_functions",
]


def _validate_operation_functions(
    entity: typing.Any, categories: dict[str, dict[str, typing.Any]]
) -> None:
    """Validate operation references against their function catalog categories."""
    for dataset in entity.datasets:
        missing = sorted(
            mapping.binding.function
            for mapping in dataset.mappings.values()
            if not any(
                mapping.binding.function in categories[category]
                for category in contracts.FUNCTION_OPERATIONS
            )
        )
        if missing:
            raise ValueError(
                f"Dataset {dataset.id} mappings reference unknown functions: " + ", ".join(missing)
            )


def _validate_binding_contract(
    binding: typing.Any,
    function: typing.Any,
    *,
    path: tuple[str | int, ...],
    additional_arguments: set[str] | None = None,
) -> None:
    """Require bound argument names to match the function template contract."""
    declared = set(function.args)
    supplied = set(binding.args) | (additional_arguments or set())
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

    def validate_selector(value: object, argument_type: str) -> None:
        if isinstance(value, str) and value.startswith("$"):
            if value.startswith(contracts.DATASET_PREFIX) and value.endswith(
                contracts.DATAFRAME_SELECTOR
            ):
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
        elif isinstance(value, list):
            element_type = argument_type[6:-1] if argument_type.startswith("array[") else "string"
            for item in value:
                validate_selector(item, element_type)
        elif isinstance(value, dict):
            value_type = (
                argument_type[12:-1] if argument_type.startswith("object{str: ") else "string"
            )
            for item in value.values():
                validate_selector(item, value_type)

    for name, value in binding.args.items():
        validate_selector(value, function.args[name].type)


def _validate_binding_contracts(
    validation_context: context_module.SpecValidationContext,
    categories: dict[str, dict[str, typing.Any]],
) -> None:
    """Validate argument names for every declared operation binding."""
    model = validation_context.model
    for entity_id, entity in model.entities.items():
        for dataset in entity.datasets:
            for mapping_id, mapping in dataset.mappings.items():
                function = next(
                    (
                        candidates[mapping.binding.function]
                        for candidates in categories.values()
                        if mapping.binding.function in candidates
                    ),
                    None,
                )
                if function is not None:
                    _validate_binding_contract(
                        mapping.binding,
                        function,
                        path=(
                            "entities",
                            entity_id,
                            "datasets",
                            dataset.id,
                            "mappings",
                            mapping_id,
                            "binding",
                            "args",
                        ),
                    )


def _validate_function_contracts(
    validation_context: context_module.SpecValidationContext,
) -> None:
    """Validate function return and dataframe-input contracts for each operation."""
    model = validation_context.model
    for function_id, function in model.functions.root.items():
        expected_returns = contracts.OPERATION_RETURN_KINDS[function.operation]
        path = ("functions", function_id)
        if function.returns != expected_returns:
            raise errors.SpecError(
                f"Operation {function.operation} must declare returns={expected_returns}",
                code="invalid_function_return_contract",
                path=(*path, "returns"),
            )
        actual_inputs = sum(argument.type == "dataframe" for argument in function.args.values())
        expected_inputs = contracts.DATAFRAME_INPUT_COUNTS[function.operation]
        if actual_inputs != expected_inputs:
            raise errors.SpecError(
                f"Operation {function.operation} requires {expected_inputs} dataframe "
                f"argument(s), got {actual_inputs}",
                code="invalid_function_input_contract",
                path=(*path, "args"),
            )
