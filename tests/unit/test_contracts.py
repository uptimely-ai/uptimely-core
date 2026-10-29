import typing

import pydantic
import pytest

from uptimely.spec import functions
from uptimely.spec import model as spec_model
from uptimely.spec.validation import bindings
from uptimely.spec.validation import context as context_module
from uptimely.spec.validation import functions as validation_functions


def test_named_function_kinds_match_the_public_contract() -> None:
    assert functions.FUNCTION_KINDS == (
        functions.WRITE,
        functions.READ,
        functions.ESCAPE,
        functions.CONFORM,
        functions.EXPAND,
        functions.COLLAPSE,
        functions.VECTORIZE,
    )
    assert typing.get_args(functions.FunctionKind) == functions.FUNCTION_KINDS
    assert set(functions.KIND_DATAFRAME_INPUT_COUNTS) == set(functions.FUNCTION_KINDS)
    assert set(functions.KIND_RETURN_KINDS) == set(functions.FUNCTION_KINDS)


@pytest.mark.parametrize(
    ("kind", "dataframe_input_count", "return_kind"),
    [
        ("read", 0, "dataframe"),
        ("write", 1, "none"),
        ("escape", None, "any"),
        ("vectorize", 1, "dataframe"),
        ("collapse", 1, "dataframe"),
        ("expand", 1, "dataframe"),
        ("conform", 1, "dataframe"),
    ],
)
def test_function_kind_contracts_validate_every_kind(
    kind: functions.FunctionKind,
    dataframe_input_count: int | None,
    return_kind: functions.FunctionReturns,
) -> None:
    assert functions.KIND_DATAFRAME_INPUT_COUNTS[kind] == dataframe_input_count
    assert functions.KIND_RETURN_KINDS[kind] == return_kind

    model = spec_model.Spec.model_validate(
        {
            "functions": {
                kind: {
                    "kind": kind,
                    "returns": return_kind,
                    "entrypoint": f"example:{kind}",
                    "args": {
                        f"dataframe_{index}": {"type": "dataframe"}
                        for index in range(dataframe_input_count or 0)
                    },
                }
            }
        }
    )
    function_id, function, dataframe_inputs = next(validation_functions.iter_functions(model))
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
                    "kind": "escape",
                    "returns": "any",
                    "entrypoint": "example:escape",
                    "args": function_args,
                }
            }
        }
    )

    function_id, function, dataframe_inputs = next(validation_functions.iter_functions(model))
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
                    "kind": "escape",
                    "returns": "any",
                    "entrypoint": "example:zero_argument",
                },
                "scalar_argument": {
                    "kind": "escape",
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
                            "actions": {
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
    for item in bindings.iter_bound_actions(validation_context.actions):
        assert bindings.validate_arguments(item) is None
        for value, argument_type in bindings.iter_binding_selectors(item):
            assert (
                bindings.validate_selector_type(
                    value,
                    argument_type,
                    (*item.location.declaration_path, "binding", "args"),
                )
                is None
            )
    for function_id, function, dataframe_inputs in validation_functions.iter_functions(model):
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
                "kind": "vectorize",
                "returns": "any",
                "entrypoint": "example:calculate",
                "args": {"dataframe": {"type": "dataframe"}},
            },
            "must declare returns=dataframe",
        ),
        (
            {
                "kind": "write",
                "returns": "none",
                "entrypoint": "example:write",
                "args": {},
            },
            "requires 1 dataframe argument",
        ),
        (
            {
                "kind": "read",
                "returns": "dataframe",
                "entrypoint": "example:read",
                "args": {"dataset": {"type": "dataframe"}},
            },
            "requires 0 dataframe argument",
        ),
        (
            {
                "kind": "conform",
                "returns": "dataframe",
                "entrypoint": "example:conform",
                "args": {
                    "source": {"type": "dataframe"},
                    "target": {"type": "dataframe"},
                },
            },
            "requires 1 dataframe argument",
        ),
    ],
)
def test_fixed_function_kind_contracts_remain_enforced(
    function: dict[str, object], expected_error: str
) -> None:
    model = spec_model.Spec.model_validate({"functions": {"function": function}})

    function_id, item, dataframe_inputs = next(validation_functions.iter_functions(model))
    error = validation_functions.validate_return_kind(
        function_id, item, dataframe_inputs
    ) or validation_functions.validate_dataframe_count(function_id, item, dataframe_inputs)
    assert isinstance(error, ValueError)
    assert expected_error in str(error)


def test_function_model_uses_the_shared_kind_contract() -> None:
    assert spec_model.FunctionTemplate.model_fields["kind"].annotation is functions.FunctionKind
    assert (
        spec_model.FunctionTemplate.model_fields["returns"].annotation is functions.FunctionReturns
    )


def test_fragment_kinds_exclude_calculations_and_sinks() -> None:
    assert set(functions.FRAGMENT_KINDS) == {"read", "conform", "expand", "collapse"}
    assert set(functions.FRAGMENT_KINDS) < set(functions.FUNCTION_KINDS)


@pytest.mark.parametrize("kind", ["python_one_liner", "sql_select", "unknown", ""])
def test_function_templates_reject_unsupported_kinds(kind: str) -> None:
    with pytest.raises(pydantic.ValidationError, match="kind"):
        spec_model.FunctionTemplate.model_validate(
            {
                "id": "calculate",
                "kind": kind,
                "returns": "dataframe",
                "entrypoint": "example:calculate",
            }
        )
