import dataclasses
import typing

import pydantic
import pytest

from uptimely.spec import functions
from uptimely.spec import model as spec_model
from uptimely.spec.validation.rules import bindings
from uptimely.spec.validation.rules import functions as validation_functions


def test_named_function_kinds_match_the_public_contract() -> None:
    expected_ids = (
        functions.WRITE,
        functions.READ,
        functions.ESCAPE,
        functions.CONFORM,
        functions.EXPAND,
        functions.COLLAPSE,
        functions.VECTORIZE,
    )
    assert tuple(functions.FUNCTION_KINDS) == expected_ids
    assert typing.get_args(functions.FunctionKindId) == expected_ids
    assert "unknown" not in functions.FUNCTION_KINDS
    assert all(kind.id == identifier for identifier, kind in functions.FUNCTION_KINDS.items())


def test_function_kind_definitions_and_registry_are_immutable() -> None:
    definition = functions.FUNCTION_KINDS[functions.READ]

    with pytest.raises(dataclasses.FrozenInstanceError):
        definition.id = functions.WRITE
    with pytest.raises(TypeError):
        functions.FUNCTION_KINDS[functions.WRITE] = definition


def test_function_kind_ids_remain_the_serialized_values() -> None:
    for kind in functions.FUNCTION_KINDS:
        model = spec_model.Spec.model_validate(
            {
                "functions": {
                    kind: {
                        "kind": kind,
                        "returns": functions.FUNCTION_KINDS[kind].returns,
                        "entrypoint": f"example:{kind}",
                    }
                }
            }
        )

        assert model.model_dump(mode="json")["functions"][kind]["kind"] == kind


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
    kind: functions.FunctionKindId,
    dataframe_input_count: int | None,
    return_kind: functions.ReturnKind,
) -> None:
    definition = functions.FUNCTION_KINDS[kind]
    assert definition.dataframe_inputs == dataframe_input_count
    assert definition.returns == return_kind

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
    assert validation_functions.validate_return_kind(model) is None
    assert validation_functions.validate_dataframe_count(model) is None


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

    assert validation_functions.validate_return_kind(model) is None
    assert validation_functions.validate_dataframe_count(model) is None


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

    assert bindings.validate_arguments(model) is None
    assert bindings.validate_selector_type(model) is None
    assert validation_functions.validate_return_kind(model) is None
    assert validation_functions.validate_dataframe_count(model) is None


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

    with pytest.raises(ValueError, match=expected_error):
        validation_functions.validate_return_kind(model)
        validation_functions.validate_dataframe_count(model)


def test_function_model_uses_the_shared_kind_contract() -> None:
    assert spec_model.FunctionTemplate.model_fields["kind"].annotation is functions.FunctionKindId
    assert spec_model.FunctionTemplate.model_fields["returns"].annotation is functions.ReturnKind


def test_function_capabilities_retain_the_current_execution_groups() -> None:
    assert all(
        definition.produces_features == (kind != functions.WRITE)
        for kind, definition in functions.FUNCTION_KINDS.items()
    )
    assert {
        kind for kind, definition in functions.FUNCTION_KINDS.items() if definition.is_source
    } == {"read", "conform", "expand", "collapse"}
    assert functions.FUNCTION_KINDS["vectorize"].is_transformer
    assert functions.FUNCTION_KINDS["write"].is_sink
    assert functions.FUNCTION_KINDS["escape"].is_effect


def test_function_kind_capabilities_can_overlap() -> None:
    source_transformer = dataclasses.replace(
        functions.FUNCTION_KINDS[functions.READ], is_transformer=True
    )

    assert source_transformer.is_source
    assert source_transformer.is_transformer


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
