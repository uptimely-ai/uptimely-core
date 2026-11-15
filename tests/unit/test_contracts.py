import dataclasses
import typing

import pydantic
import pytest

from uptimely.spec import model as spec_model
from uptimely.spec import operator_bindings


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


def test_binding_contracts_distinguish_primary_bindings_from_merge() -> None:
    contracts = operator_bindings.OPERATOR_BINDINGS
    assert {name for name, contract in contracts.items() if contract.primary} == set(
        typing.get_args(operator_bindings.PrimaryBindingKind.__value__)
    )
    assert not contracts["merge"].primary
    assert contracts["compute"].dataframe_inputs == (0, 1)
    assert contracts["merge"].dataframe_inputs == (2,)
    with pytest.raises(dataclasses.FrozenInstanceError):
        contracts["compute"].description = "changed"
    with pytest.raises(TypeError):
        contracts["compute"] = contracts["merge"]


def test_operator_execution_contracts_derive_from_bound_dataframe_sources() -> None:
    spec = _shared_callable_spec()
    local_key = ("local", "self_transform")
    remote_key = ("remote", "foreign_transform")
    local = spec.operators_by_key[local_key]
    remote = spec.operators_by_key[remote_key]

    local_contract = local.execution_contract(
        returns="dataframe",
        target_profile="local",
        dataframe_sources=("local",),
        grain_relationships={"local": "same"},
    )
    remote_contract = remote.execution_contract(
        returns="dataframe",
        target_profile="remote",
        dataframe_sources=("local",),
        grain_relationships={"local": "same"},
    )

    assert local_contract.is_transformer
    assert local_contract.dataframe_input_scope == "target"
    assert local_contract.row_count_relation == "same"
    assert local_contract.key_relation == "identical"
    assert local.produces_target_features(spec, local_key)
    assert remote_contract.is_source
    assert remote_contract.dataframe_input_scope == "foreign"
    assert remote_contract.feature_input_scope == "dataframe"
    assert remote_contract.dimension_change == "preserve"
    assert remote_contract.fragment_dimensions == "target"
    assert not remote.produces_target_features(spec, remote_key)


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


def test_one_callable_can_have_distinct_operator_source_relationships() -> None:
    spec = _shared_callable_spec()

    assert (
        spec.operators_by_key["local", "self_transform"].grain_relationships(
            spec, ("local", "self_transform")
        )["local"]
        == "same"
    )
    assert (
        spec.operators_by_key["remote", "foreign_transform"].grain_relationships(
            spec, ("remote", "foreign_transform")
        )["local"]
        == "same"
    )
    assert spec.functions["shared"].returns == "dataframe"
    assert not hasattr(spec.functions["shared"], "kind")


def test_function_contract_round_trips_without_kind_metadata() -> None:
    spec = _shared_callable_spec()
    payload = spec.model_dump(mode="json")

    assert payload["spec_version"] == 9
    assert "kind" not in payload["functions"]["shared"]
    reloaded = spec_model.Spec.model_validate(payload)
    assert reloaded.model_dump(mode="json") == payload
