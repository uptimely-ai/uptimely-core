import dataclasses
import json

import pytest

from uptimely import execution_plan as uptimely_plan


def _sample_plan() -> uptimely_plan.ExecutionPlan:
    return uptimely_plan.ExecutionPlan(
        plan_version=1,
        required_backend="polars",
        resources={
            "signatures": {
                "callable:read:load:pump:pump_dataset:pressure": "DataFrame",
                "callable:write:save:pump:pump_dataset:pressure_by_pump": "None",
            }
        },
        callables=[
            uptimely_plan.Callable(
                id="callable:read:load:pump:pump_dataset:pressure",
                operation="read",
                entrypoint="example.functions:load",
                entity_id="pump",
                dataset_id="pump_dataset",
                output="pressure",
                arguments={"dataset": {"type": "literal", "value": "pump_dataset"}},
                dependency_ids=[],
            ),
            uptimely_plan.Callable(
                id="callable:collapse:maximum:pump:pump_dataset:pressure_by_pump",
                operation="collapse",
                entrypoint="example.functions:maximum",
                entity_id="pump",
                dataset_id="pump_dataset",
                output="pressure_by_pump",
                arguments={"feature": "pressure"},
                output_features=["plant", "pump", "maximum"],
                dependency_ids=["callable:read:load:pump:pump_dataset:pressure"],
            ),
            uptimely_plan.Callable(
                id="callable:write:save:pump:pump_dataset:pressure_by_pump",
                operation="write",
                entrypoint="example.functions:save",
                entity_id="pump",
                dataset_id="pump_dataset",
                output="pressure_by_pump",
                arguments={},
                dependency_ids=["callable:collapse:maximum:pump:pump_dataset:pressure_by_pump"],
            ),
        ],
        stages=[
            ["callable:read:load:pump:pump_dataset:pressure"],
            ["callable:collapse:maximum:pump:pump_dataset:pressure_by_pump"],
            ["callable:write:save:pump:pump_dataset:pressure_by_pump"],
        ],
    )


def test_plan_round_trip_preserves_operation_metadata() -> None:
    plan = _sample_plan()

    payload = uptimely_plan.to_dict(plan)
    restored = uptimely_plan.from_dict(payload)

    assert restored == plan
    assert restored.callables[1].function_id == "maximum"
    assert not hasattr(restored.callables[1], "source")
    assert all("source" not in callable for callable in payload["callables"])
    assert restored.callables[1].entrypoint == "example.functions:maximum"
    assert restored.callables[1].entity_id == "pump"
    assert restored.callables[1].output == "pressure_by_pump"
    assert restored.callables[0].dataset_id == "pump_dataset"


def test_plan_stages_track_callable_order() -> None:
    plan = _sample_plan()

    assert plan.stages == [
        ["callable:read:load:pump:pump_dataset:pressure"],
        ["callable:collapse:maximum:pump:pump_dataset:pressure_by_pump"],
        ["callable:write:save:pump:pump_dataset:pressure_by_pump"],
    ]
    assert [[callable.function_id for callable in stage] for stage in plan.execution_stages] == [
        ["load"],
        ["maximum"],
        ["save"],
    ]

    restored = uptimely_plan.from_dict(uptimely_plan.to_dict(plan))
    assert restored.stages == plan.stages


def test_execution_plan_serializes_only_the_portable_plan() -> None:
    plan = _sample_plan()
    payload = uptimely_plan.to_dict(plan)

    assert payload == uptimely_plan.to_dict(uptimely_plan.from_dict(payload))
    assert set(payload) == {
        "plan_version",
        "required_backend",
        "resources",
        "callables",
        "stages",
    }


def test_plan_json_helpers_round_trip(tmp_path) -> None:
    plan = _sample_plan()
    destination = tmp_path / "plan.json"

    uptimely_plan.export_json(plan, destination)
    payload = json.loads(destination.read_text(encoding="utf-8"))
    recreated = uptimely_plan.from_json(destination)

    assert payload["callables"][0]["operation"] == "read"
    assert recreated == plan
    assert recreated.callables[0].id == "callable:read:load:pump:pump_dataset:pressure"


@pytest.mark.parametrize("missing_field", ["callables", "required_backend", "stages"])
def test_plan_rejects_missing_required_fields(missing_field: str) -> None:
    payload = uptimely_plan.to_dict(_sample_plan())
    del payload[missing_field]

    with pytest.raises(ValueError, match=f"Plan is missing required fields: {missing_field}"):
        uptimely_plan.from_dict(payload)


def test_plan_rejects_spec_version_field() -> None:
    payload = uptimely_plan.to_dict(_sample_plan())
    payload["spec_version"] = 1

    with pytest.raises(ValueError, match="Plan contains unknown fields: spec_version"):
        uptimely_plan.from_dict(payload)


@pytest.mark.parametrize("version", [0, 2, "1", "unsupported", None, True])
def test_plan_rejects_unsupported_versions(version: object) -> None:
    payload = uptimely_plan.to_dict(_sample_plan())
    payload["plan_version"] = version

    with pytest.raises(ValueError, match="Unsupported plan version"):
        uptimely_plan.from_dict(payload)
    with pytest.raises(ValueError, match="Unsupported plan version"):
        uptimely_plan.ExecutionPlan(**{**_sample_plan().__dict__, "plan_version": version})


def test_plan_rejects_unknown_dependency_and_stage_callable() -> None:
    payload = uptimely_plan.to_dict(_sample_plan())
    payload["callables"][1]["dependency_ids"] = ["unknown-callable"]
    payload["stages"][2] = ["another-unknown-operation"]

    with pytest.raises(ValueError, match="Plan references unknown callable"):
        uptimely_plan.from_dict(payload)


def test_plan_rejects_duplicate_and_unstaged_callables() -> None:
    duplicate_payload = uptimely_plan.to_dict(_sample_plan())
    duplicate_payload["callables"].append(dict(duplicate_payload["callables"][0]))

    with pytest.raises(ValueError, match="duplicate callable ids"):
        uptimely_plan.from_dict(duplicate_payload)

    unstaged_payload = uptimely_plan.to_dict(_sample_plan())
    unstaged_payload["stages"] = unstaged_payload["stages"][:-1]

    with pytest.raises(ValueError, match="must stage every callable exactly once"):
        uptimely_plan.from_dict(unstaged_payload)


def test_plan_rejects_dependencies_scheduled_after_consumers() -> None:
    payload = uptimely_plan.to_dict(_sample_plan())
    payload["stages"][0], payload["stages"][1] = payload["stages"][1], payload["stages"][0]

    with pytest.raises(ValueError, match="must be scheduled before"):
        uptimely_plan.from_dict(payload)


def test_direct_execution_plan_construction_validates_structure() -> None:
    plan = _sample_plan()
    cases = [
        (
            {"callables": [*plan.callables, plan.callables[0]]},
            "duplicate callable ids",
        ),
        (
            {
                "callables": [
                    dataclasses.replace(plan.callables[0], dependency_ids=["unknown-callable"]),
                    *plan.callables[1:],
                ]
            },
            "references unknown callable",
        ),
        (
            {"stages": [*plan.stages, plan.stages[-1]]},
            "stage every callable exactly once",
        ),
        (
            {"stages": [plan.stages[1], plan.stages[0], plan.stages[2]]},
            "must be scheduled before",
        ),
    ]

    for changes, message in cases:
        with pytest.raises(ValueError, match=message):
            dataclasses.replace(plan, **changes)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("entrypoint", None, "must declare an entrypoint"),
        ("entrypoint", "", "must declare an entrypoint"),
        ("output_features", [], "must declare output_features"),
    ],
)
def test_plan_rejects_invalid_collapse_metadata(field: str, value: object, message: str) -> None:
    payload = uptimely_plan.to_dict(_sample_plan())
    payload["callables"][1][field] = value
    with pytest.raises(ValueError, match=message):
        uptimely_plan.from_dict(payload)


@pytest.mark.parametrize("field", ["source", "group_by", "operations"])
def test_plan_rejects_removed_collapse_fields(field: str) -> None:
    payload = uptimely_plan.to_dict(_sample_plan())
    payload["callables"][1][field] = []
    with pytest.raises(TypeError, match=field):
        uptimely_plan.from_dict(payload)
