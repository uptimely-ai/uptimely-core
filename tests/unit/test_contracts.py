import types

import pytest

from uptimely import contracts
from uptimely.spec import model as spec_model
from uptimely.spec import resolved
from uptimely.spec.validation import functions as validation_functions
from uptimely.spec.validation import prepared


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

    function = spec_model.FunctionTemplate(
        id=operation,
        operation=operation,
        returns=return_kind,
        entrypoint="module:function",
        args={
            f"frame_{index}": spec_model.Argument(id=f"frame_{index}", type="dataframe")
            for index in range(dataframe_input_count)
        },
    )
    model = types.SimpleNamespace(functions=types.SimpleNamespace(root={operation: function}))
    validation_context = types.SimpleNamespace(model=model)

    validation_functions._validate_function_contracts(validation_context)


def test_function_model_reexports_the_shared_operation_contract() -> None:
    assert spec_model.FUNCTION_OPERATIONS is contracts.FUNCTION_OPERATIONS


def test_fragment_operations_exclude_calculations_and_sinks() -> None:
    assert set(contracts.FRAGMENT_OPERATIONS) == {"read", "conform", "expand", "collapse"}
    assert set(contracts.FRAGMENT_OPERATIONS) < set(contracts.FUNCTION_OPERATIONS)


@pytest.mark.parametrize("function_type", ["python_one_liner", "sql_select", "unknown"])
def test_resolved_functions_reject_unsupported_types(function_type: str) -> None:
    function = resolved.Function(
        id="calculate", type=function_type, info={}, entrypoint="pl.col('reading')"
    )

    with pytest.raises(ValueError, match=f"unsupported operation type: {function_type}"):
        prepared._validate_function_definitions([function])
