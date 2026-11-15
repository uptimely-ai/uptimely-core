import pytest

from uptimely.spec import model, validation


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
    key = ("target", "calculate")
    operator = spec.operators_by_key[key]
    source_profiles, source_status = operator.source_details(spec, key)
    relationships = operator.grain_relationships(spec, key)

    assert source_profiles == ("source",)
    assert source_status == "resolved"
    assert relationships["source"] == relationship
    assert operator.profile_resolutions(spec, "source") == tuple(
        spec.dimensions[dimension].resolutions[resolution] for dimension, resolution in source
    )
    assert operator.profile_resolutions(spec, "target") == tuple(
        spec.dimensions[dimension].resolutions[resolution] for dimension, resolution in target
    )


def test_spec_reports_operator_with_no_source() -> None:
    spec = _make_spec(None, [("scope", "root")])
    key = ("target", "calculate")
    operator = spec.operators_by_key[key]

    assert operator.source_details(spec, key) == ((), "missing")
    assert operator.grain_relationships(spec, key) == {None: "not_applicable"}
    assert operator.profile_resolutions(spec, "target") == (
        spec.dimensions["scope"].resolutions["root"],
    )


def test_spec_exposes_calculated_feature_producers() -> None:
    spec_definition = _make_spec([("scope", "root")], [("scope", "root")])
    operator = spec_definition.profiles["target"].assembly["calculate"]
    operator.compute.args["data"] = model.BindingArgument(root="$profiles.target.dataset")
    spec_definition = spec_definition.rebuild()
    key = ("target", "calculate")

    operator = spec_definition.operators_by_key[key]
    assert operator.produces_target_features(spec_definition, key) is True
    assert spec_definition.calculated_feature_producers == {
        "result": ("target", spec_definition.profiles["target"].assembly["calculate"])
    }


def test_existing_operator_exposes_binding_and_output_declarations() -> None:
    spec = _make_spec([("scope", "root")], [("scope", "root")])
    key = ("target", "calculate")
    operator = spec.operators_by_key[key]
    assert operator.execution_form == "compute"
    assert operator.binding_roles == ("compute",)
    operator.merge = model.Binding(function="custom_merge", args={})

    assert operator.execution_form == "compute + merge"
    assert operator.binding_roles == ("compute", "merge")
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
    key = ("target", "calculate")
    operator = spec.operators_by_key[key]
    source_profiles, source_status = operator.source_details(spec, key)
    relationships = operator.grain_relationships(spec, key)

    assert source_profiles == ("source", "other_source")
    assert source_status == "ambiguous"
    assert relationships == {
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
        spec.operators_by_key["target", "calculate"].source_details(spec, ("target", "calculate"))[
            1
        ]
        == "invalid_reference"
    )

    def fail_if_derived(self: model.Operator, *args: object) -> None:
        raise AssertionError(f"Unexpected relationship derivation before reference checks: {args}")

    monkeypatch.setattr(model.Operator, "_grain_relationship", fail_if_derived)
    with pytest.raises(ValueError, match="references unknown profile: missing"):
        validation.validate_spec(spec)


def test_dimension_hierarchy_is_validated_before_grain_relationships(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = _make_spec([("scope", "root")], [("scope", "child")])
    spec.dimensions["scope"].resolutions["root"].parent = "child"

    def fail_if_derived(self: model.Operator, *args: object) -> None:
        raise AssertionError(f"Unexpected relationship derivation before hierarchy checks: {args}")

    monkeypatch.setattr(model.Operator, "_grain_relationship", fail_if_derived)
    with pytest.raises(validation.SpecError) as error:
        validation.validate_spec(spec)

    assert error.value.code == "dimension_resolution_parent_cycle"


def test_operator_semantics_are_refreshed_by_rebuild() -> None:
    spec = _make_spec([("scope", "root")], [("scope", "root")])
    key = ("target", "calculate")
    previous_relationships = spec.operators_by_key[key].grain_relationships(spec, key)
    spec.profiles["target"].grain = [model.Grain(dimension="scope", resolution="child")]

    rebuilt = spec.rebuild()

    assert previous_relationships["source"] == "same"
    assert rebuilt.operators_by_key[key].grain_relationships(rebuilt, key)["source"] == "expand"


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
    assert (
        spec.operators_by_key["target", "calculate"].compute.function
        == spec.operators_by_key["expanded", "calculate"].compute.function
        == "transform"
    )
    assert (
        spec.operators_by_key["target", "calculate"].grain_relationships(
            spec, ("target", "calculate")
        )["source"]
        == "same"
    )
    assert (
        spec.operators_by_key["expanded", "calculate"].grain_relationships(
            spec, ("expanded", "calculate")
        )["source"]
        == "expand"
    )
