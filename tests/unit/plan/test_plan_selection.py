import pytest
from support import execution as execution_support

from uptimely import plan as uptimely_plan


def _sample_plan() -> uptimely_plan.ExecutionPlan:
    return uptimely_plan.ExecutionPlan(
        plan_version=uptimely_plan.PLAN_VERSION,
        required_backend="polars",
        invocations=[
            uptimely_plan.Invocation(
                id="opaque-read",
                entrypoint="example.src:load",
                arguments={"dataset": {"type": "literal", "value": "pump_profile"}},
                returns="pump_profile",
                semantics=uptimely_plan.InvocationSemantics(
                    role="compute",
                    result="target",
                    dataframe_input_scope="none",
                    function_id="load",
                    operator_id="read_pressure",
                    profile_id="pump_profile",
                    dependency_ids=[],
                    target_identifiers=["plant", "pump"],
                    fragment_keys=["plant", "pump"],
                    output_types={"pressure": "float"},
                    column_types={"plant": "string", "pump": "string", "pressure": "float"},
                    argument_types={"dataset": "dataframe"},
                    return_type="DataFrame",
                    package=uptimely_plan.Package(distribution="example-package", version="1.0"),
                ),
            ),
            uptimely_plan.Invocation(
                id="opaque-collapse",
                entrypoint="example.src:maximum",
                arguments={"feature": "pressure"},
                returns="pump_profile",
                semantics=uptimely_plan.InvocationSemantics(
                    role="compute",
                    result="target",
                    dataframe_input_scope="foreign",
                    function_id="maximum",
                    operator_id="pressure_by_pump",
                    profile_id="pump_profile",
                    output_features=["plant", "pump", "maximum"],
                    dependency_ids=["opaque-read"],
                ),
            ),
            uptimely_plan.Invocation(
                id="opaque-write",
                entrypoint="example.src:save",
                arguments={},
                semantics=uptimely_plan.InvocationSemantics(
                    role="compute",
                    result="none",
                    function_id="save",
                    operator_id="save_pressure_by_pump",
                    profile_id="pump_profile",
                    dependency_ids=["opaque-collapse"],
                ),
            ),
        ],
        stages=[
            ["opaque-read"],
            ["opaque-collapse"],
            ["opaque-write"],
        ],
    )


def test_operator_selection_preserves_dependencies_and_saved_order() -> None:
    original = _sample_plan()

    selected = original.for_operator("pump_profile", "pressure_by_pump")

    assert original.invocations_by_id["opaque-read"].returns == "pump_profile"
    assert original.invocations_by_id["opaque-collapse"].returns == "pump_profile"
    assert original.invocations_by_id["opaque-write"].returns is None
    assert list(selected.invocations_by_id) == ["opaque-read", "opaque-collapse"]
    assert [stage.root for stage in selected.stages] == [["opaque-read"], ["opaque-collapse"]]
    assert selected.invocations[1].semantics.dependency_ids == ["opaque-read"]
    assert "opaque-write" in original.invocations_by_id


def test_operator_selection_includes_explicit_sink() -> None:
    original = _sample_plan()

    assert original.for_operator("pump_profile", "save_pressure_by_pump") == original


@pytest.mark.parametrize(
    ("profile_id", "operator_id"),
    [("unknown", "pressure_by_pump"), ("pump_profile", "unknown")],
)
def test_operator_selection_rejects_unknown_target(profile_id: str, operator_id: str) -> None:
    with pytest.raises(ValueError, match="not in the saved execution scope"):
        _sample_plan().for_operator(profile_id, operator_id)


def test_operator_selection_retains_fragment_merge_pairs() -> None:
    original = uptimely_plan.from_json("tests/fixtures/plans/simple_engine.json")

    selected = original.for_operator("telemetry", "reading")

    assert {invocation.semantics.role for invocation in selected.invocations} == {
        "compute",
        "merge",
    }
    assert {invocation.semantics.operator_id for invocation in selected.invocations} == {"reading"}
    assert [invocation.semantics.role for invocation in selected.execution_invocations] == [
        "compute",
        "merge",
    ]


def test_plan_round_trip_preserves_execution_metadata() -> None:
    plan = _sample_plan()

    payload = uptimely_plan.to_dict(plan)
    restored = uptimely_plan.from_dict(payload)

    assert restored == plan
    assert restored.invocations[1].semantics.function_id == "maximum"
    assert restored.invocations[1].entrypoint == "example.src:maximum"
    assert restored.invocations[1].semantics.profile_id == "pump_profile"
    assert restored.invocations[1].semantics.operator_id == "pressure_by_pump"
    assert restored.invocations[0].semantics.function_id == "load"
    assert restored.invocations[0].semantics.operator_id == "read_pressure"
    assert restored.invocations[0].semantics.profile_id == "pump_profile"
    assert restored.invocations[0].semantics.target_identifiers == ["plant", "pump"]
    assert restored.invocations[0].semantics.output_types == {"pressure": "float"}
    assert restored.invocations[0].semantics.column_types == {
        "plant": "string",
        "pump": "string",
        "pressure": "float",
    }
    assert restored.invocations[0].semantics.argument_types == {"dataset": "dataframe"}
    assert all("profile_id" in invocation["semantics"] for invocation in payload["invocations"])


def test_plan_round_trip_preserves_expansion_key_columns() -> None:
    original = _sample_plan()
    invocation = original.invocations[1].__replace__(
        semantics=original.invocations[1].semantics.__replace__(fragment_keys=["series"])
    )
    plan = original.__replace__(
        invocations=[original.invocations[0], invocation, original.invocations[2]]
    )

    restored = uptimely_plan.from_dict(uptimely_plan.to_dict(plan))

    assert restored == plan
    assert restored.invocations[1].semantics.fragment_keys == ["series"]


def test_plan_requires_fragment_identifier_metadata() -> None:
    payload = uptimely_plan.to_dict(_sample_plan())
    for invocation in payload["invocations"]:
        invocation["semantics"].pop("fragment_keys")

    with pytest.raises(ValueError, match="missing runtime metadata: fragment_keys"):
        uptimely_plan.from_dict(payload)


def test_plan_rejects_version_twelve_before_loading_invocations() -> None:
    payload = uptimely_plan.to_dict(_sample_plan())
    payload["plan_version"] = 12
    with pytest.raises(ValueError, match="Unsupported plan version: 12.*Recompile"):
        uptimely_plan.from_dict(payload)


def test_support_return_contract_comes_from_invocation_metadata() -> None:
    invocation = _sample_plan().invocations[0]
    invocation = invocation.__replace__(
        semantics=invocation.semantics.__replace__(
            result="none",
            is_sink=False,
        )
    )

    assert execution_support._return_contract_from_invocation(invocation) == "any"


def test_plan_round_trip_preserves_read_key_columns() -> None:
    original = _sample_plan()
    reader = original.invocations[0].__replace__(
        semantics=original.invocations[0].semantics.__replace__(
            fragment_keys=["series", "category"]
        )
    )
    plan = original.__replace__(invocations=[reader, *original.invocations[1:]])

    restored = uptimely_plan.from_dict(uptimely_plan.to_dict(plan))

    assert restored == plan
    assert restored.invocations[0].semantics.fragment_keys == ["series", "category"]


@pytest.mark.parametrize(
    "field",
    [
        "target_identifiers",
        "fragment_keys",
        "output_types",
        "produces_features",
        "is_sink",
        "dataframe_input_scope",
        "fragment_dimensions",
        "row_count_relation",
        "key_relation",
        "row_order_relation",
        "existing_data_relation",
        "column_types",
        "argument_types",
        "return_type",
        "package",
    ],
)
def test_plan_requires_runtime_metadata_in_saved_invocations(field: str) -> None:
    payload = uptimely_plan.to_dict(_sample_plan())
    del payload["invocations"][0]["semantics"][field]

    with pytest.raises(ValueError, match=f"missing runtime metadata: {field}.*Recompile"):
        uptimely_plan.from_dict(payload)


def test_plan_stages_track_invocation_order() -> None:
    plan = _sample_plan()

    assert all(isinstance(stage, uptimely_plan.Stage) for stage in plan.stages)
    assert [stage.invocation_ids for stage in plan.stages] == [
        ["opaque-read"],
        ["opaque-collapse"],
        ["opaque-write"],
    ]
    assert [
        [invocation.semantics.function_id for invocation in stage]
        for stage in plan.execution_stages
    ] == [["load"], ["maximum"], ["save"]]

    restored = uptimely_plan.from_dict(uptimely_plan.to_dict(plan))
    assert restored.stages == plan.stages
    assert uptimely_plan.to_dict(plan)["stages"] == [
        ["opaque-read"],
        ["opaque-collapse"],
        ["opaque-write"],
    ]


def test_execution_plan_serializes_only_the_portable_plan() -> None:
    plan = _sample_plan()
    payload = uptimely_plan.to_dict(plan)

    assert payload == uptimely_plan.to_dict(uptimely_plan.from_dict(payload))
    assert set(payload) == {
        "plan_version",
        "required_backend",
        "invocations",
        "stages",
    }
    assert payload["plan_version"] == uptimely_plan.PLAN_VERSION
    assert {"function_id", "operator_id"} <= set(payload["invocations"][0]["semantics"])
    assert payload["invocations"][0]["semantics"]["role"] == "compute"
    assert payload["invocations"][0]["semantics"]["result"] == "target"
    assert payload["invocations"][0]["semantics"]["return_type"] == "DataFrame"
    assert payload["invocations"][0]["semantics"]["package"] == {
        "distribution": "example-package",
        "version": "1.0",
    }


def test_plan_json_helpers_round_trip(tmp_path) -> None:
    plan = _sample_plan()
    destination = tmp_path / "plan.json"

    uptimely_plan.export_json(plan, destination)
    recreated = uptimely_plan.from_json(destination)

    assert recreated == plan
    assert recreated.invocations[0].id == "opaque-read"
