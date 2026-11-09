import dataclasses
import typing

import pydantic
import pytest

from uptimely.spec import model as spec_model
from uptimely.spec import operator_kinds


def _shared_callable_spec() -> spec_model.Spec:
    return spec_model.Spec.model_validate(
        {
            "functions": {
                "shared": {
                    "returns": "dataframe",
                    "entrypoint": "example:transform",
                    "args": {"dataset": {"type": "dataframe"}},
                }
            },
            "profiles": {
                "local": {
                    "assembly": {
                        "self_transform": {
                            "compute": {
                                "function": "shared",
                                "args": {"dataset": "$profiles.@.dataset"},
                            },
                            "interface": {"inputs": [], "outputs": []},
                        }
                    }
                },
                "remote": {
                    "assembly": {
                        "foreign_transform": {
                            "compute": {
                                "function": "shared",
                                "args": {"dataset": "$profiles.local.dataset"},
                            },
                            "interface": {"inputs": [], "outputs": []},
                        }
                    }
                },
            },
        }
    )


def test_named_operator_kinds_match_the_public_contract() -> None:
    expected_ids = (
        operator_kinds.WRITE,
        operator_kinds.READ,
        operator_kinds.ESCAPE,
        operator_kinds.CONFORM,
        operator_kinds.EXPAND,
        operator_kinds.COLLAPSE,
        operator_kinds.VECTORIZE,
        operator_kinds.MERGE,
    )
    assert tuple(operator_kinds.OPERATOR_KINDS) == expected_ids
    assert typing.get_args(operator_kinds.OperatorKindId) == expected_ids
    assert "unknown" not in operator_kinds.OPERATOR_KINDS
    assert all(kind.id == identifier for identifier, kind in operator_kinds.OPERATOR_KINDS.items())


def test_operator_kind_definitions_and_registry_are_immutable() -> None:
    definition = operator_kinds.OPERATOR_KINDS[operator_kinds.READ]
    with pytest.raises(dataclasses.FrozenInstanceError):
        definition.id = operator_kinds.WRITE
    with pytest.raises(TypeError):
        operator_kinds.OPERATOR_KINDS[operator_kinds.WRITE] = definition


@pytest.mark.parametrize(
    ("kind", "produces_fragment", "dimension_change", "fragment_dimensions"),
    [
        ("read", True, "unrestricted", "target"),
        ("write", False, "unrestricted", "not_applicable"),
        ("escape", False, "unrestricted", "not_applicable"),
        ("conform", True, "preserve", "target"),
        ("expand", True, "add", "subset"),
        ("collapse", True, "remove", "target"),
        ("vectorize", False, "preserve", "not_applicable"),
    ],
)
def test_operator_policies_remain_independent_of_callable_contracts(
    kind: operator_kinds.OperatorKindId,
    produces_fragment: bool,
    dimension_change: operator_kinds.DimensionChange,
    fragment_dimensions: operator_kinds.FragmentDimensions,
) -> None:
    definition = operator_kinds.OPERATOR_KINDS[kind]
    assert definition.produces_fragment is produces_fragment
    assert definition.dimension_change == dimension_change
    assert definition.fragment_dimensions == fragment_dimensions


def test_function_template_contract_has_roles_but_no_operator_kind() -> None:
    fields = spec_model.FunctionTemplate.model_fields
    assert "kind" not in fields
    assert fields["returns"].is_required()

    template = spec_model.FunctionTemplate.model_validate(
        {"id": "calculate", "returns": "any", "entrypoint": "example:calculate"}
    )
    assert template.returns == "any"
    assert not hasattr(template, "kind")

    with pytest.raises(pydantic.ValidationError, match="returns"):
        spec_model.FunctionTemplate.model_validate(
            {"id": "calculate", "entrypoint": "example:calculate"}
        )


def test_one_callable_can_have_different_usage_derived_operator_labels() -> None:
    spec = _shared_callable_spec()

    assert spec.operator_kinds == {
        ("local", "self_transform"): "vectorize",
        ("remote", "foreign_transform"): "conform",
    }
    assert spec.functions["shared"].returns == "dataframe"
    assert not hasattr(spec.functions["shared"], "kind")


def test_function_contract_round_trips_without_kind_metadata() -> None:
    spec = _shared_callable_spec()
    payload = spec.model_dump(mode="json")

    assert payload["spec_version"] == 8
    assert "kind" not in payload["functions"]["shared"]
    reloaded = spec_model.Spec.model_validate(payload)
    assert reloaded.model_dump(mode="json") == payload
