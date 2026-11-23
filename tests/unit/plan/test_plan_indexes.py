import copy

from uptimely import plan as uptimely_plan


def _sample_plan() -> uptimely_plan.ExecutionPlan:
    return uptimely_plan.ExecutionPlan(
        plan_version=uptimely_plan.PLAN_VERSION,
        required_backend="polars",
        invocations=[
            uptimely_plan.Invocation(
                id="opaque-read",
                entrypoint="example.src:load",
                arguments={},
                returns="$datasets.pump.read",
                semantics=uptimely_plan.InvocationSemantics(
                    role="compute",
                    result="target",
                    function_id="load",
                    operator_id="read_pressure",
                    profile_id="pump_profile",
                    target_identifiers=["plant", "pump"],
                ),
            ),
            uptimely_plan.Invocation(
                id="opaque-collapse",
                entrypoint="example.src:maximum",
                arguments={"dataset": "$datasets.pump.read"},
                returns="$dataset.pump.maximum",
                semantics=uptimely_plan.InvocationSemantics(
                    role="compute",
                    result="target",
                    function_id="maximum",
                    operator_id="pressure_by_pump",
                    profile_id="pump_profile",
                    output_features=["maximum"],
                ),
            ),
            uptimely_plan.Invocation(
                id="opaque-write",
                entrypoint="example.src:save",
                arguments={"dataset": "$dataset.pump.maximum"},
                returns=None,
                semantics=uptimely_plan.InvocationSemantics(
                    role="compute",
                    result="none",
                    function_id="save",
                    operator_id="save_pressure_by_pump",
                    profile_id="pump_profile",
                    is_sink=True,
                ),
            ),
        ],
        stages=[
            ["opaque-read"],
            ["opaque-collapse"],
            ["opaque-write"],
        ],
        datasets={"pump": "$dataset.pump.maximum"},
    )


def test_plan_indexes_explicit_references_and_declared_metadata() -> None:
    plan = _sample_plan()

    assert list(plan.invocations_by_id) == ["opaque-read", "opaque-collapse", "opaque-write"]
    assert plan.function_ids == {"load", "maximum", "save"}
    assert plan.profile_ids == {"pump_profile"}
    assert plan.features == {"maximum": [plan.invocations[1]]}
    assert plan.calculated_features == {"maximum"}
    assert list(plan.entrypoints) == [
        "example.src:load",
        "example.src:maximum",
        "example.src:save",
    ]
    assert plan.input_invocations == {
        "opaque-read": [],
        "opaque-collapse": ["opaque-read"],
        "opaque-write": ["opaque-collapse"],
    }
    assert plan.count_per_role == {"compute": 3}
    assert plan.execution_stages == [[invocation] for invocation in plan.invocations]
    assert plan.execution_invocations == plan.invocations


def test_plan_replacement_does_not_retain_stale_indexes() -> None:
    plan = _sample_plan()
    original_index = plan.invocations_by_id
    original_execution = plan.execution_invocations
    original_features = plan.features
    replacement = copy.replace(
        plan.invocations[1],
        semantics=copy.replace(plan.invocations[1].semantics, output_features=["changed"]),
    )
    plan.invocations[1] = replacement
    assert "changed" not in original_features
    assert plan.features is original_features
    plan = copy.replace(plan)
    assert plan.invocations_by_id is not original_index
    assert plan.invocations_by_id[replacement.id] is replacement
    assert plan.features["changed"] == [replacement]
    assert plan.execution_stages[1] == [replacement]
    assert plan.execution_invocations is not original_execution
    assert plan.execution_invocations[1] is replacement

    copied = copy.replace(plan)
    assert copied.invocations_by_id is not plan.invocations_by_id
    assert copied.invocations_by_id == plan.invocations_by_id


def test_execution_invocations_follow_stages_not_declaration_order() -> None:
    original = _sample_plan()
    plan = copy.replace(original, invocations=list(reversed(original.invocations)))
    assert plan.invocations != original.invocations
    assert plan.execution_invocations == original.invocations
    assert uptimely_plan.to_dict(plan)["invocations"][0]["id"] == "opaque-write"

    empty = copy.replace(
        original,
        invocations=[],
        stages=[],
        datasets={},
    )
    assert empty.execution_invocations == []
    assert empty.count_per_role == {}


def test_count_per_role_rebuilt_on_plan_replacement() -> None:
    plan = _sample_plan()
    previous = plan.count_per_role
    plan.invocations[0] = copy.replace(
        plan.invocations[0],
        semantics=copy.replace(
            plan.invocations[0].semantics,
            result="fragment",
            fragment_dimensions="target",
        ),
    )
    plan.invocations[1] = copy.replace(
        plan.invocations[1],
        semantics=copy.replace(
            plan.invocations[1].semantics,
            role="merge",
            operator_id="read_pressure",
        ),
    )
    assert plan.count_per_role is previous
    plan = copy.replace(plan)
    assert plan.count_per_role == {"compute": 2, "merge": 1}
    assert plan.count_per_role is not previous
