import dataclasses
import json

import pytest

from uptimely import execution_plan as uptimely_plan


def _sample_plan() -> uptimely_plan.ExecutionPlan:
    return uptimely_plan.ExecutionPlan(
        plan_version=2,
        required_backend="polars",
        resources={
            "signatures": {
                "opaque-read": "DataFrame",
                "opaque-write": "None",
            }
        },
        invocations=[
            uptimely_plan.Invocation(
                id="opaque-read",
                operation="read",
                entrypoint="example.functions:load",
                function_id="load",
                mapping_id="read_pressure",
                entity_id="pump",
                dataset_id="pump_dataset",
                arguments={"dataset": {"type": "literal", "value": "pump_dataset"}},
                dependency_ids=[],
            ),
            uptimely_plan.Invocation(
                id="opaque-collapse",
                operation="collapse",
                entrypoint="example.functions:maximum",
                function_id="maximum",
                mapping_id="pressure_by_pump",
                entity_id="pump",
                dataset_id="pump_dataset",
                arguments={"feature": "pressure"},
                output_features=["plant", "pump", "maximum"],
                dependency_ids=["opaque-read"],
            ),
            uptimely_plan.Invocation(
                id="opaque-write",
                operation="write",
                entrypoint="example.functions:save",
                function_id="save",
                mapping_id="save_pressure_by_pump",
                entity_id="pump",
                dataset_id="pump_dataset",
                arguments={},
                dependency_ids=["opaque-collapse"],
            ),
        ],
        stages=[
            ["opaque-read"],
            ["opaque-collapse"],
            ["opaque-write"],
        ],
    )


def test_plan_round_trip_preserves_operation_metadata() -> None:
    plan = _sample_plan()

    payload = uptimely_plan.to_dict(plan)
    restored = uptimely_plan.from_dict(payload)

    assert restored == plan
    assert restored.invocations[1].function_id == "maximum"
    assert not hasattr(restored.invocations[1], "source")
    assert all("source" not in invocation for invocation in payload["invocations"])
    assert restored.invocations[1].entrypoint == "example.functions:maximum"
    assert restored.invocations[1].entity_id == "pump"
    assert restored.invocations[1].mapping_id == "pressure_by_pump"
    assert restored.invocations[0].function_id == "load"
    assert restored.invocations[0].mapping_id == "read_pressure"
    assert restored.invocations[0].dataset_id == "pump_dataset"


def test_plan_stages_track_invocation_order() -> None:
    plan = _sample_plan()

    assert plan.stages == [
        ["opaque-read"],
        ["opaque-collapse"],
        ["opaque-write"],
    ]
    assert [
        [invocation.function_id for invocation in stage] for stage in plan.execution_stages
    ] == [["load"], ["maximum"], ["save"]]

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
        "invocations",
        "stages",
    }
    assert payload["plan_version"] == 2
    assert {"function_id", "mapping_id"} <= set(payload["invocations"][0])
    assert "output" not in payload["invocations"][0]


def test_plan_json_helpers_round_trip(tmp_path) -> None:
    plan = _sample_plan()
    destination = tmp_path / "plan.json"

    uptimely_plan.export_json(plan, destination)
    payload = json.loads(destination.read_text(encoding="utf-8"))
    recreated = uptimely_plan.from_json(destination)

    assert payload["invocations"][0]["operation"] == "read"
    assert recreated == plan
    assert recreated.invocations[0].id == "opaque-read"


@pytest.mark.parametrize(
    "missing_field", ["plan_version", "invocations", "required_backend", "stages"]
)
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


def test_plan_rejects_version_one_with_supported_version_error() -> None:
    payload = uptimely_plan.to_dict(_sample_plan())
    payload["plan_version"] = 1
    payload["callables"] = payload.pop("invocations")

    with pytest.raises(ValueError, match=r"Unsupported plan version: 1\. Supported version is 2\."):
        uptimely_plan.from_dict(payload)


@pytest.mark.parametrize("version", [0, 1, 3, "2", "unsupported", None, True])
def test_plan_rejects_unsupported_versions(version: object) -> None:
    payload = uptimely_plan.to_dict(_sample_plan())
    payload["plan_version"] = version

    with pytest.raises(ValueError, match="Unsupported plan version"):
        uptimely_plan.from_dict(payload)
    with pytest.raises(ValueError, match="Unsupported plan version"):
        uptimely_plan.ExecutionPlan(**{**_sample_plan().__dict__, "plan_version": version})


def test_plan_rejects_unknown_dependency_and_stage_invocation() -> None:
    payload = uptimely_plan.to_dict(_sample_plan())
    payload["invocations"][1]["dependency_ids"] = ["unknown-invocation"]
    payload["stages"][2] = ["another-unknown-operation"]

    with pytest.raises(ValueError, match="Plan references unknown invocation"):
        uptimely_plan.from_dict(payload)


def test_plan_rejects_duplicate_and_unstaged_invocations() -> None:
    duplicate_payload = uptimely_plan.to_dict(_sample_plan())
    duplicate_payload["invocations"].append(dict(duplicate_payload["invocations"][0]))

    with pytest.raises(ValueError, match="duplicate invocation ids"):
        uptimely_plan.from_dict(duplicate_payload)

    unstaged_payload = uptimely_plan.to_dict(_sample_plan())
    unstaged_payload["stages"] = unstaged_payload["stages"][:-1]

    with pytest.raises(ValueError, match="must stage every invocation exactly once"):
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
            {"invocations": [*plan.invocations, plan.invocations[0]]},
            "duplicate invocation ids",
        ),
        (
            {
                "invocations": [
                    dataclasses.replace(plan.invocations[0], dependency_ids=["unknown-invocation"]),
                    *plan.invocations[1:],
                ]
            },
            "references unknown invocation",
        ),
        (
            {"stages": [*plan.stages, plan.stages[-1]]},
            "stage every invocation exactly once",
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
    payload["invocations"][1][field] = value
    with pytest.raises(ValueError, match=message):
        uptimely_plan.from_dict(payload)


@pytest.mark.parametrize("field", ["output", "source", "group_by", "operations"])
def test_plan_rejects_removed_collapse_fields(field: str) -> None:
    payload = uptimely_plan.to_dict(_sample_plan())
    payload["invocations"][1][field] = []
    with pytest.raises(TypeError, match=field):
        uptimely_plan.from_dict(payload)
