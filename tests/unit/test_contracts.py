import pydantic
import pytest

from uptimely import contracts
from uptimely.spec import model as spec_model
from uptimely.spec.validation import functions as validation_functions


@pytest.mark.parametrize(
    ("operation", "dataframe_input_count", "return_kind"),
    [
        ("read", 0, "dataframe"),
        ("write", 1, "none"),
        ("vectorize", 1, "dataframe"),
        ("collapse", 1, "dataframe"),
        ("expand", 2, "dataframe"),
        ("conform", 2, "dataframe"),
    ],
)
def test_operation_contracts_validate_every_function_operation(
    operation: contracts.FunctionOperation,
    dataframe_input_count: int,
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
    validation_functions._validate_dataframe_argument_count(
        operation,
        contracts.DATAFRAME_INPUT_COUNTS[operation],
        dataframe_input_count,
        path=("functions", operation, "args"),
    )


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
