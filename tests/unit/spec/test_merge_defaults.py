"""Default merge resolution for Python and JSON-authored Specs."""

import json

import pytest

from uptimely.spec import api, validation
from uptimely.spec import model as spec_model
from uptimely.spec.python import Spec, assembly, feature, profile, ref


def _operator(
    operator_id: str,
    kind: str = "read",
    *,
    merge: assembly.Binding | None = None,
) -> assembly.Operator:
    return assembly.Operator(
        id=operator_id,
        interface=assembly.Interface(outputs=[feature.Feature(id=f"value_{operator_id}")]),
        compute=assembly.Binding(function=ref.function(f"reader:{operator_id}", kind=kind)),
        merge=merge,
    )


def _resolved_python_spec(
    operators: list[assembly.Operator],
) -> spec_model.Spec:
    return Spec(profiles=[profile.Profile(id="readings", assembly=operators)]).to_model()


def test_fragment_operators_receive_builtin_bindings_and_catalog_entry() -> None:
    document = _resolved_python_spec([_operator("read")])
    operator = document.profiles["readings"].assembly["read"]

    assert operator.merge is not None
    default_function = spec_model.merge.DEFAULT_FUNCTION
    assert operator.merge.function == default_function.id
    assert "merge_source" not in operator.model_dump()
    assert operator.merge.args == {
        "target": spec_model.BindingArgument("$profiles.@.dataframe"),
        "fragment": spec_model.BindingArgument("$operators.@.fragment"),
        "target_keys": spec_model.BindingArgument("$profiles.@.grain.ids"),
    }
    assert document.functions[default_function.id] == default_function
    reloaded = spec_model.Spec.model_validate(document.model_dump())
    assert reloaded.model_dump() == document.model_dump()


def test_auto_bindings_pass_spec_validation() -> None:
    document = api.from_python(
        profiles=[profile.Profile(id="readings", assembly=[_operator("read")])]
    )

    assert (
        document.profiles["readings"].assembly["read"].merge.function
        == spec_model.merge.DEFAULT_FUNCTION.id
    )


def test_direct_spec_model_validation_resolves_merge_bindings() -> None:
    payload = _resolved_python_spec([_operator("read")]).model_dump()
    payload["profiles"]["readings"]["assembly"]["read"]["merge"] = None
    payload["functions"].pop(spec_model.merge.DEFAULT_FUNCTION.id)

    document = spec_model.Spec.model_validate(payload)

    assert document.profiles["readings"].assembly["read"].merge is not None
    assert (
        document.profiles["readings"].assembly["read"].merge.function
        == spec_model.merge.DEFAULT_FUNCTION.id
    )


def test_each_fragment_operator_receives_a_default_merge_binding() -> None:
    document = _resolved_python_spec([_operator("read_first"), _operator("read_second")])

    assert all(operator.merge is not None for operator in document.operators)
    assert all(
        operator.merge.function == spec_model.merge.DEFAULT_FUNCTION.id
        for operator in document.operators
    )


def test_user_binding_takes_precedence() -> None:
    custom_merge = assembly.Binding(
        function=ref.function("merger:combine", kind="merge"),
        arguments={"target": ref.dataset(), "fragment": ref.fragment()},
    )
    document = _resolved_python_spec([_operator("read", merge=custom_merge)])

    operator = document.profiles["readings"].assembly["read"]
    assert operator.merge is not None
    assert operator.merge.function == "combine"
    assert spec_model.merge.DEFAULT_FUNCTION.id not in document.functions


def test_vectorize_is_not_counted_as_a_fragment_producer() -> None:
    operator = assembly.Operator(
        id="calculate",
        interface=assembly.Interface(outputs=[feature.Feature(id="calculated")]),
        compute=assembly.Binding(
            function=ref.function("calculator:calculate", kind="vectorize"),
            arguments={"dataset": ref.dataset()},
        ),
    )

    document = _resolved_python_spec([operator])
    assert document.profiles["readings"].assembly["calculate"].merge is None
    assert spec_model.merge.DEFAULT_FUNCTION.id not in document.functions


def test_json_loading_uses_the_same_resolution_and_is_idempotent(tmp_path) -> None:
    unresolved = _resolved_python_spec([_operator("read")]).model_dump()
    unresolved["profiles"]["readings"]["assembly"]["read"]["merge"] = None
    unresolved["functions"].pop(spec_model.merge.DEFAULT_FUNCTION.id)
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(unresolved), encoding="utf-8")

    loaded = api.load_spec(path)
    resolved_again = spec_model.Spec.model_validate(loaded.model_dump())
    assert (
        loaded.profiles["readings"].assembly["read"].merge.function
        == spec_model.merge.DEFAULT_FUNCTION.id
    )
    assert resolved_again.model_dump() == loaded.model_dump()


def test_builtin_function_id_conflicts_are_not_overwritten() -> None:
    document = _resolved_python_spec([_operator("read")])
    profile_model = document.profiles["readings"]
    operator = profile_model.assembly["read"].model_copy(update={"merge": None})
    profile_model = profile_model.model_copy(update={"assembly": {"read": operator}})
    functions = dict(document.functions.root)
    default_function = spec_model.merge.DEFAULT_FUNCTION
    functions[default_function.id] = spec_model.FunctionTemplate(
        id=default_function.id,
        kind="merge",
        returns="dataframe",
        entrypoint="custom:merge",
        args={
            "target": spec_model.Argument(id="target", type="dataframe | null"),
            "fragment": spec_model.Argument(id="fragment", type="dataframe"),
            "target_keys": spec_model.Argument(id="target_keys", type="array[string]"),
        },
    )
    conflicting = document.model_copy(
        update={
            "profiles": {"readings": profile_model},
            "functions": spec_model.FunctionCatalog(root=functions),
        }
    )

    parsed = spec_model.Spec.model_validate(conflicting.model_dump())

    with pytest.raises(ValueError, match="conflicts with the builtin"):
        validation.validate_spec(parsed)
