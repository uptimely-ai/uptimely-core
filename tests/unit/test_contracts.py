import pydantic
import pytest

from uptimely import contracts
from uptimely.spec import model as spec_model
from uptimely.spec.validation import context as context_module
from uptimely.spec.validation import functions as validation_functions


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
    operation: contracts.FunctionOperation,
    dataframe_input_count: int | None,
    return_kind: contracts.FunctionReturns,
) -> None:
    assert contracts.DATAFRAME_INPUT_COUNTS[operation] == dataframe_input_count
    assert contracts.OPERATION_RETURN_KINDS[operation] == return_kind

    validation_functions._validate_return_kind(
        operation,
        return_kind,
        contracts.OPERATION_RETURN_KINDS[operation],
        path=("functions", operation, "returns"),
    )
    if dataframe_input_count is not None:
        validation_functions._validate_dataframe_argument_count(
            operation,
            dataframe_input_count,
            dataframe_input_count,
            path=("functions", operation, "args"),
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

    validation_functions.validate_contracts(context_module.SpecValidationContext.build(model))


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
                    "datasets": [
                        {
                            "id": "dataset",
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
                            },
                        }
                    ],
                }
            },
        }
    )

    validation_context = context_module.SpecValidationContext.build(model)
    validation_functions.validate_bindings(validation_context)
    validation_functions.validate_contracts(validation_context)


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

    with pytest.raises(ValueError, match=expected_error):
        validation_functions.validate_contracts(context_module.SpecValidationContext.build(model))


def test_function_model_reexports_the_shared_operation_contract() -> None:
    assert spec_model.FUNCTION_OPERATIONS is contracts.FUNCTION_OPERATIONS


def test_fragment_operations_exclude_calculations_and_sinks() -> None:
    assert set(contracts.FRAGMENT_OPERATIONS) == {"read", "conform", "expand", "collapse"}
    assert set(contracts.FRAGMENT_OPERATIONS) < set(contracts.FUNCTION_OPERATIONS)


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
