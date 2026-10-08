import json

import pytest

from uptimely.plan import ExecutionPlan, Operation, Plan, export_json, from_json


def _sample_plan() -> Plan:
    return Plan(
        plan_version="1.0.0",
        specification_version="2024.01",
        required_backend="polars",
        resources={
            "signatures": {
                "callable:read:load:pump:pump_dataset:pressure": "DataFrame",
                "callable:collapse:aggregate:pump:pump_dataset:pressure_by_pump": "DataFrame",
                "callable:write:save:pump:pump_dataset:pressure_by_pump": "None",
            }
        },
        operations=[
            Operation(
                id="callable:read:load:pump:pump_dataset:pressure",
                kind="read",
                entrypoint="example.functions:load",
                entity_id="pump",
                dataset_id="pump_dataset",
                output="pressure",
                arguments={"dataset": {"type": "literal", "value": "pump_dataset"}},
                dependency_ids=[],
            ),
            Operation(
                id="callable:collapse:aggregate:pump:pump_dataset:pressure_by_pump",
                kind="collapse",
                entrypoint="example.functions:aggregate",
                entity_id="pump",
                dataset_id="pump_dataset",
                output="pressure_by_pump",
                arguments={"dimensions": {"type": "literal", "value": ["plant", "pump"]}},
                dependency_ids=["callable:read:load:pump:pump_dataset:pressure"],
            ),
            Operation(
                id="callable:write:save:pump:pump_dataset:pressure_by_pump",
                kind="write",
                entrypoint="example.functions:save",
                entity_id="pump",
                dataset_id="pump_dataset",
                output="pressure_by_pump",
                arguments={},
                dependency_ids=["callable:collapse:aggregate:pump:pump_dataset:pressure_by_pump"],
            ),
        ],
        stages=[
            ["callable:read:load:pump:pump_dataset:pressure"],
            ["callable:collapse:aggregate:pump:pump_dataset:pressure_by_pump"],
            ["callable:write:save:pump:pump_dataset:pressure_by_pump"],
        ],
    )


def test_plan_round_trip_preserves_operation_metadata() -> None:
    plan = _sample_plan()

    payload = plan.to_dict()
    restored = Plan.from_dict(payload)

    assert restored == plan
    assert restored.operations[1].function_id == "aggregate"
    assert restored.operations[1].entity == "pump"
    assert restored.operations[1].feature is None
    assert restored.operations[0].dataset_id == "pump_dataset"


def test_plan_stages_track_operation_order() -> None:
    plan = _sample_plan()
    execution_plan = ExecutionPlan(plan)

    assert plan.stages == [
        ["callable:read:load:pump:pump_dataset:pressure"],
        ["callable:collapse:aggregate:pump:pump_dataset:pressure_by_pump"],
        ["callable:write:save:pump:pump_dataset:pressure_by_pump"],
    ]
    assert [
        [operation.function_id for operation in stage] for stage in execution_plan.execution_stages
    ] == [["load"], ["aggregate"], ["save"]]
    assert [operation.function_id for operation in execution_plan.execution_order] == [
        "load",
        "aggregate",
        "save",
    ]

    restored = Plan.from_dict(plan.to_dict())
    assert restored.stages == plan.stages


def test_execution_plan_exposes_legacy_execution_views() -> None:
    plan = _sample_plan()
    execution_plan = ExecutionPlan(plan)

    legacy = execution_plan.to_dict()
    assert legacy["execution_stages"][1]["steps"][0]["position"] == 2
    assert legacy["execution_order"][1]["depends_on_callables"][0]["function"] == "load"
    assert legacy["execution_order"][2]["returns"]["type"] == {"engine": "None"}
    assert legacy["spec_version"] == "2024.01"


def test_plan_json_helpers_round_trip(tmp_path) -> None:
    plan = _sample_plan()
    destination = tmp_path / "plan.json"

    export_json(plan, destination)
    payload = json.loads(destination.read_text(encoding="utf-8"))
    recreated = from_json(destination)

    assert payload["operations"][0]["kind"] == "read"
    assert payload["execution_order"][0]["function"] == "load"
    assert recreated.plan == plan
    assert recreated.operations[0].id == "callable:read:load:pump:pump_dataset:pressure"


@pytest.mark.parametrize("missing_field", ["operations", "required_backend", "stages"])
def test_plan_rejects_missing_required_fields(missing_field: str) -> None:
    payload = _sample_plan().to_dict()
    del payload[missing_field]

    with pytest.raises(ValueError, match=f"Plan is missing required fields: {missing_field}"):
        Plan.from_dict(payload)


def test_plan_rejects_unknown_dependency_and_stage_operation() -> None:
    payload = _sample_plan().to_dict()
    payload["operations"][1]["dependency_ids"] = ["unknown-operation"]
    payload["stages"][2] = ["another-unknown-operation"]

    with pytest.raises(ValueError, match="Plan references unknown operation"):
        Plan.from_dict(payload)


def test_plan_rejects_duplicate_and_unstaged_operations() -> None:
    duplicate_payload = _sample_plan().to_dict()
    duplicate_payload["operations"].append(dict(duplicate_payload["operations"][0]))

    with pytest.raises(ValueError, match="duplicate operation ids"):
        Plan.from_dict(duplicate_payload)

    unstaged_payload = _sample_plan().to_dict()
    unstaged_payload["stages"] = unstaged_payload["stages"][:-1]

    with pytest.raises(ValueError, match="must stage every operation exactly once"):
        Plan.from_dict(unstaged_payload)


def test_plan_rejects_dependencies_scheduled_after_consumers() -> None:
    payload = _sample_plan().to_dict()
    payload["stages"][0], payload["stages"][1] = payload["stages"][1], payload["stages"][0]

    with pytest.raises(ValueError, match="must be scheduled before"):
        Plan.from_dict(payload)
