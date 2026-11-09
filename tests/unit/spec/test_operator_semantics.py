import pytest

from uptimely.spec import model, semantics, validation


def _make_spec(
    source_grain: list[tuple[str, str]] | None,
    target_grain: list[tuple[str, str]],
) -> model.Spec:
    profiles: dict[str, dict[str, object]] = {
        "target": {
            "grain": [
                {"dimension": dimension, "resolution": resolution}
                for dimension, resolution in target_grain
            ],
            "features": {"result": {}},
            "assembly": {
                "calculate": {
                    "compute": {
                        "function": "transform",
                        "args": (
                            {"data": "$profiles.source.dataset"} if source_grain is not None else {}
                        ),
                    },
                    "interface": {
                        "inputs": ["$features.signal"] if source_grain is not None else [],
                        "outputs": ["$features.result"],
                    },
                }
            },
        }
    }
    if source_grain is not None:
        profiles["source"] = {
            "grain": [
                {"dimension": dimension, "resolution": resolution}
                for dimension, resolution in source_grain
            ],
            "features": {"signal": {}},
        }
    return model.Spec.model_validate(
        {
            "dimensions": {
                "scope": {
                    "resolutions": {
                        "root": {"key": "root_id", "type": "string"},
                        "child": {"key": "child_id", "type": "string", "parent": "root"},
                        "left": {"key": "left_id", "type": "string", "parent": "root"},
                        "right": {"key": "right_id", "type": "string", "parent": "root"},
                    }
                }
            },
            "functions": {
                "transform": {
                    "returns": "dataframe",
                    "entrypoint": "example:transform",
                    "args": ({"data": {"type": "dataframe"}} if source_grain is not None else {}),
                }
            },
            "profiles": profiles,
        }
    )


@pytest.mark.parametrize(
    ("source", "target", "relationship"),
    [
        ([("scope", "root")], [("scope", "root")], "same"),
        ([], [("scope", "child")], "expand"),
        ([("scope", "root")], [("scope", "child")], "expand"),
        ([("scope", "child")], [("scope", "root")], "collapse"),
        ([("scope", "left")], [("scope", "right")], "unrelated"),
    ],
)
def test_spec_classifies_profile_grains_using_resolution_hierarchy(
    source: list[tuple[str, str]],
    target: list[tuple[str, str]],
    relationship: str,
) -> None:
    spec = _make_spec(source, target)
    spec_semantics = semantics.Semantics(spec)
    key = ("target", "calculate")

    assert spec_semantics.operator_source_profile_keys[key] == ("source",)
    assert spec_semantics.operator_source_statuses[key] == "resolved"
    assert spec_semantics.operator_grain_relationships[key]["source"] == relationship
    assert spec_semantics.operator_source_resolutions[key]["source"] == tuple(
        spec.dimensions[dimension].resolutions[resolution] for dimension, resolution in source
    )
    assert spec_semantics.operator_target_resolutions[key] == tuple(
        spec.dimensions[dimension].resolutions[resolution] for dimension, resolution in target
    )


def test_spec_reports_operator_with_no_source() -> None:
    spec = _make_spec(None, [("scope", "root")])
    spec_semantics = semantics.Semantics(spec)
    key = ("target", "calculate")

    assert spec_semantics.operator_source_profile_keys[key] == ()
    assert spec_semantics.operator_source_statuses[key] == "missing"
    assert spec_semantics.operator_grain_relationships[key] == {None: "not_applicable"}
    assert spec_semantics.operator_target_resolutions[key] == (
        spec.dimensions["scope"].resolutions["root"],
    )


def test_existing_operator_exposes_binding_and_output_declarations() -> None:
    spec = _make_spec([("scope", "root")], [("scope", "root")])
    spec_semantics = semantics.Semantics(spec)
    key = ("target", "calculate")
    operator = spec.operators_by_key[key]
    operator.merge = model.Binding(function="custom_merge", args={})

    assert spec_semantics.operator_execution_forms[key] == "compute + merge"
    assert spec_semantics.operator_binding_roles[key] == ("compute", "merge")
    assert not hasattr(spec, "operator_execution_forms")
    assert list(operator.bindings) == ["compute", "merge"]
    assert operator.bindings["compute"] is operator.compute
    assert operator.bindings["merge"] is operator.merge
    assert operator.output_features == ["result"]


def test_spec_reports_ambiguous_feature_sources() -> None:
    spec = _make_spec([("scope", "root")], [("scope", "root")])
    spec.profiles["other_source"] = model.Profile(
        id="other_source",
        grain=[model.Grain(dimension="scope", resolution="root")],
        features={"signal": model.Feature(id="signal")},
    )
    spec = spec.rebuild()
    spec_semantics = semantics.Semantics(spec)
    key = ("target", "calculate")

    assert spec_semantics.operator_source_profile_keys[key] == ("source", "other_source")
    assert spec_semantics.operator_source_statuses[key] == "ambiguous"
    assert spec_semantics.operator_grain_relationships[key] == {
        "source": "same",
        "other_source": "same",
        None: "not_applicable",
    }


def test_invalid_profile_reference_is_rejected_before_relationship_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = _make_spec([("scope", "root")], [("scope", "root")])
    spec.profiles["target"].assembly["calculate"].compute.args["data"] = model.BindingArgument(
        "$profiles.missing.dataset"
    )

    assert (
        semantics.Semantics(spec).operator_source_statuses["target", "calculate"]
        == "invalid_reference"
    )

    def fail_if_derived(self: semantics.Semantics, *args: object) -> None:
        raise AssertionError(
            f"Unexpected relationship derivation before reference checks: {self.spec.name}, {args}"
        )

    monkeypatch.setattr(semantics.Semantics, "_grain_relationship", fail_if_derived)
    with pytest.raises(ValueError, match="references unknown profile: missing"):
        validation.validate_spec(spec)


def test_dimension_hierarchy_is_validated_before_grain_relationships(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = _make_spec([("scope", "root")], [("scope", "child")])
    spec.dimensions["scope"].resolutions["root"].parent = "child"

    def fail_if_derived(self: semantics.Semantics, *args: object) -> None:
        raise AssertionError(
            f"Unexpected relationship derivation before hierarchy checks: {self.spec.name}, {args}"
        )

    monkeypatch.setattr(semantics.Semantics, "_grain_relationship", fail_if_derived)
    with pytest.raises(validation.SpecError) as error:
        validation.validate_spec(spec)

    assert error.value.code == "dimension_resolution_parent_cycle"


def test_operator_semantics_are_refreshed_by_rebuild() -> None:
    spec = _make_spec([("scope", "root")], [("scope", "root")])
    key = ("target", "calculate")
    previous_semantics = semantics.Semantics(spec)
    previous_relationships = previous_semantics.operator_grain_relationships[key]
    spec.profiles["target"].grain = [model.Grain(dimension="scope", resolution="child")]

    rebuilt = spec.rebuild()

    assert previous_semantics.operator_grain_relationships[key] is previous_relationships
    assert semantics.Semantics(rebuilt).operator_grain_relationships[key]["source"] == "expand"


def test_shared_function_can_have_distinct_operator_relationships() -> None:
    spec = _make_spec([("scope", "root")], [("scope", "root")])
    spec.profiles["expanded"] = model.Profile(
        id="expanded",
        grain=[model.Grain(dimension="scope", resolution="child")],
        features={"result": model.Feature(id="result")},
        assembly={
            "calculate": model.Operator(
                id="calculate",
                compute=model.Binding(
                    function="transform",
                    args={"data": "$profiles.source.dataset"},
                ),
                interface=model.Interface(
                    inputs=["$features.signal"],
                    outputs=["$features.result"],
                ),
            )
        },
    )
    spec = spec.rebuild()
    spec_semantics = semantics.Semantics(spec)

    assert (
        spec.operators_by_key["target", "calculate"].compute.function
        == spec.operators_by_key["expanded", "calculate"].compute.function
        == "transform"
    )
    assert spec_semantics.operator_grain_relationships["target", "calculate"]["source"] == "same"
    assert (
        spec_semantics.operator_grain_relationships["expanded", "calculate"]["source"] == "expand"
    )
