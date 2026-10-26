import typing

import pydantic
import pytest

from uptimely.spec import model as spec_model
from uptimely.spec import operations
from uptimely.spec.validation import bindings
from uptimely.spec.validation import context as context_module
from uptimely.spec.validation import functions as validation_functions


def test_named_operations_match_the_public_operation_contract() -> None:
    assert operations.FUNCTION_OPERATIONS == (
        operations.READ,
        operations.WRITE,
        operations.ESCAPE,
        operations.VECTORIZE,
        operations.COLLAPSE,
        operations.EXPAND,
        operations.CONFORM,
    )
    assert typing.get_args(operations.FunctionOperation) == operations.FUNCTION_OPERATIONS
    assert set(operations.DATAFRAME_INPUT_COUNTS) == set(operations.FUNCTION_OPERATIONS)
    assert set(operations.OPERATION_RETURN_KINDS) == set(operations.FUNCTION_OPERATIONS)


@pytest.mark.parametrize(
    ("operation", "dataframe_input_count", "return_kind"),
    [
        ("read", 0, "dataframe"),
        ("write", 1, "none"),
        ("escape", None, "any"),
        ("vectorize", 1, "dataframe"),
        ("collapse", 1, "dataframe"),
        ("expand", 2, "dataframe"),
        ("conform", 2, "dataframe"),
    ],
)
def test_operation_contracts_validate_every_function_operation(
    operation: operations.FunctionOperation,
    dataframe_input_count: int | None,
    return_kind: operations.FunctionReturns,
) -> None:
    assert operations.DATAFRAME_INPUT_COUNTS[operation] == dataframe_input_count
    assert operations.OPERATION_RETURN_KINDS[operation] == return_kind

    model = spec_model.Spec.model_validate(
        {
            "functions": {
                operation: {
                    "operation": operation,
                    "returns": return_kind,
                    "entrypoint": f"example:{operation}",
                    "args": {
                        f"dataframe_{index}": {"type": "dataframe"}
                        for index in range(dataframe_input_count or 0)
                    },
                }
            }
        }
    )
    function_id, function, dataframe_inputs = next(
        context_module.SpecValidationContext.build(model).iter_functions()
    )
    assert (
        validation_functions.validate_return_kind(function_id, function, dataframe_inputs) is None
    )
    assert (
        validation_functions.validate_dataframe_count(function_id, function, dataframe_inputs)
        is None
    )


@pytest.mark.parametrize("dataframe_input_count", [0, 1, 3])
def test_escape_contract_accepts_any_number_of_dataframe_arguments(
    dataframe_input_count: int,
) -> None:
    function_args = {
        f"dataframe_{index}": {"type": "dataframe"} for index in range(dataframe_input_count)
    }
    model = spec_model.Spec.model_validate(
        {
            "functions": {
                "escape": {
                    "operation": "escape",
                    "returns": "any",
                    "entrypoint": "example:escape",
                    "args": function_args,
                }
            }
        }
    )

    function_id, function, dataframe_inputs = next(
        context_module.SpecValidationContext.build(model).iter_functions()
    )
    assert (
        validation_functions.validate_return_kind(function_id, function, dataframe_inputs) is None
    )
    assert (
        validation_functions.validate_dataframe_count(function_id, function, dataframe_inputs)
        is None
    )


def test_escape_binding_validation_accepts_scalar_and_zero_arguments() -> None:
    model = spec_model.Spec.model_validate(
        {
            "functions": {
                "zero_argument": {
                    "operation": "escape",
                    "returns": "any",
                    "entrypoint": "example:zero_argument",
                },
                "scalar_argument": {
                    "operation": "escape",
                    "returns": "any",
                    "entrypoint": "example:scalar_argument",
                    "args": {"value": {"type": "float"}},
                },
            },
            "entities": {
                "entity": {
                    "name": "Entity",
                    "datasets": {
                        "dataset": {
                            "mappings": {
                                "zero_argument": {
                                    "binding": {"function": "zero_argument", "args": {}}
                                },
                                "scalar_argument": {
                                    "binding": {
                                        "function": "scalar_argument",
                                        "args": {"value": 1.5},
                                    }
                                },
                            }
                        }
                    },
                }
            },
        }
    )

    validation_context = context_module.SpecValidationContext.build(model)
    for item in validation_context.iter_bound_mappings():
        assert bindings.validate_arguments(item) is None
        for value, argument_type in validation_context.iter_binding_selectors(item):
            assert (
                bindings.validate_selector_type(
                    value,
                    argument_type,
                    (*item.location.declaration_path, "binding", "args"),
                )
                is None
            )
    for function_id, function, dataframe_inputs in validation_context.iter_functions():
        assert (
            validation_functions.validate_return_kind(function_id, function, dataframe_inputs)
            is None
        )
        assert (
            validation_functions.validate_dataframe_count(function_id, function, dataframe_inputs)
            is None
        )


@pytest.mark.parametrize(
    ("function", "expected_error"),
    [
        (
            {
                "operation": "vectorize",
                "returns": "any",
                "entrypoint": "example:calculate",
                "args": {"dataframe": {"type": "dataframe"}},
            },
            "must declare returns=dataframe",
        ),
        (
            {
                "operation": "write",
                "returns": "none",
                "entrypoint": "example:write",
                "args": {},
            },
            "requires 1 dataframe argument",
        ),
    ],
)
def test_fixed_operation_contracts_remain_enforced(
    function: dict[str, object], expected_error: str
) -> None:
    model = spec_model.Spec.model_validate({"functions": {"function": function}})

    function_id, item, dataframe_inputs = next(
        context_module.SpecValidationContext.build(model).iter_functions()
    )
    error = validation_functions.validate_return_kind(
        function_id, item, dataframe_inputs
    ) or validation_functions.validate_dataframe_count(function_id, item, dataframe_inputs)
    assert isinstance(error, ValueError)
    assert expected_error in str(error)


def test_function_model_reexports_the_shared_operation_contract() -> None:
    assert spec_model.FUNCTION_OPERATIONS is operations.FUNCTION_OPERATIONS


def test_fragment_operations_exclude_calculations_and_sinks() -> None:
    assert set(operations.FRAGMENT_OPERATIONS) == {"read", "conform", "expand", "collapse"}
    assert set(operations.FRAGMENT_OPERATIONS) < set(operations.FUNCTION_OPERATIONS)


@pytest.mark.parametrize("operation", ["python_one_liner", "sql_select", "unknown", ""])
def test_function_templates_reject_unsupported_operations(operation: str) -> None:
    with pytest.raises(pydantic.ValidationError, match="operation"):
        spec_model.FunctionTemplate.model_validate(
            {
                "id": "calculate",
                "operation": operation,
                "returns": "dataframe",
                "entrypoint": "example:calculate",
            }
        )
