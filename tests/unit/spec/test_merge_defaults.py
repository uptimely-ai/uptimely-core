"""Explicit selection of the builtin grain merge."""

import json

from uptimely import default_merge, merge
from uptimely.spec import model as spec_model
from uptimely.spec.python import Spec, assembly, feature, profile, ref


def _operator(operator_id: str, *, merge: assembly.Binding | None = None) -> assembly.Operator:
    return assembly.Operator(
        id=operator_id,
        interface=assembly.Interface(outputs=[feature.Feature(id=f"value_{operator_id}")]),
        compute=assembly.Binding(
            function=ref.function(f"reader:{operator_id}", returns="dataframe")
        ),
        merge=merge,
    )


def _python_spec(operators: list[assembly.Operator]) -> spec_model.Spec:
    return Spec(profiles=[profile.Profile(id="readings", assembly=operators)]).to_model()


def test_omitted_merge_is_not_implicit() -> None:
    document = _python_spec([_operator("read")])
    operator = document.profiles["readings"].assembly["read"]

    assert operator.merge is None
    assert "merge_by_grain" not in document.functions
    assert "__uptimely_merge_by_grain" not in document.functions
    assert (
        spec_model.Spec.model_validate(document.model_dump()).model_dump() == document.model_dump()
    )


def test_default_merge_helper_returns_an_explicit_binding() -> None:
    binding = merge.default()
    document = _python_spec([_operator("read", merge=binding)])
    operator = document.profiles["readings"].assembly["read"]

    assert operator.merge is not None
    assert operator.merge.function == "merge_by_grain"
    assert operator.merge.args == {
        "dataset": spec_model.BindingArgument("$profiles.@.dataset"),
        "fragment": spec_model.BindingArgument("$operators.@.fragment"),
        "dataset_identifiers": spec_model.BindingArgument("$profiles.@.grain.ids"),
    }
    assert "merge_by_grain" in document.functions
    assert document.functions["merge_by_grain"].returns == "dataframe"
    assert (
        spec_model.Spec.model_validate(document.model_dump()).model_dump() == document.model_dump()
    )


def test_legacy_helper_remains_an_alias() -> None:
    assert default_merge is merge.default


def test_json_round_trip_preserves_explicit_default_binding(tmp_path) -> None:
    document = _python_spec([_operator("read", merge=merge.default())])
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(document.model_dump(mode="json")), encoding="utf-8")

    restored = spec_model.Spec.model_validate(json.loads(path.read_text(encoding="utf-8")))

    assert restored.model_dump(mode="json") == document.model_dump(mode="json")
    assert restored.profiles["readings"].assembly["read"].merge.function == "merge_by_grain"


def test_explicit_builtin_reference_collects_its_contract() -> None:
    document = _python_spec([_operator("read", merge=merge.default())])
    payload = document.model_dump(mode="json")
    payload["functions"].pop("merge_by_grain")

    restored = spec_model.Spec.model_validate(payload)

    assert restored.profiles["readings"].assembly["read"].merge.function == "merge_by_grain"
    assert "merge_by_grain" in restored.functions
