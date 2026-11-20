import copy

import pytest

from uptimely import plan as uptimely_plan


def _sample_plan() -> uptimely_plan.ExecutionPlan:
    return uptimely_plan.ExecutionPlan(
        plan_version=uptimely_plan.PLAN_VERSION,
        required_backend="polars",
        invocations=[
            uptimely_plan.Invocation(
                id="opaque-read",
                role="compute",
                result="target",
                dataframe_input_scope="none",
                entrypoint="example.src:load",
                function_id="load",
                operator_id="read_pressure",
                profile_id="pump_profile",
                arguments={"dataset": {"type": "literal", "value": "pump_profile"}},
                dependency_ids=[],
                target_identifiers=["plant", "pump"],
                fragment_keys=["plant", "pump"],
                output_types={"pressure": "float"},
                column_types={"plant": "string", "pump": "string", "pressure": "float"},
                argument_types={"dataset": "dataframe"},
                return_type="DataFrame",
                package=uptimely_plan.Package(distribution="example-package", version="1.0"),
            ),
            uptimely_plan.Invocation(
                id="opaque-collapse",
                role="compute",
                result="target",
                dataframe_input_scope="foreign",
                entrypoint="example.src:maximum",
                function_id="maximum",
                operator_id="pressure_by_pump",
                profile_id="pump_profile",
                arguments={"feature": "pressure"},
                output_features=["plant", "pump", "maximum"],
                dependency_ids=["opaque-read"],
            ),
            uptimely_plan.Invocation(
                id="opaque-write",
                role="compute",
                result="none",
                entrypoint="example.src:save",
                function_id="save",
                operator_id="save_pressure_by_pump",
                profile_id="pump_profile",
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


@pytest.mark.parametrize(
    "missing_field",
    [
        "plan_version",
        "invocations",
        "required_backend",
        "stages",
    ],
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

    with pytest.raises(
        ValueError, match=r"Unsupported plan version: 1\. Supported version is 14\."
    ):
        uptimely_plan.from_dict(payload)


@pytest.mark.parametrize(
    "version", [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, "11", "unsupported", None, True]
)
def test_plan_rejects_unsupported_versions(version: object) -> None:
    payload = uptimely_plan.to_dict(_sample_plan())
    payload["plan_version"] = version

    with pytest.raises(ValueError, match="Unsupported plan version"):
        uptimely_plan.from_dict(payload)
    with pytest.raises(ValueError, match="Unsupported plan version"):
        copy.replace(_sample_plan(), plan_version=version)


def test_version_six_plan_requires_rebuilding() -> None:
    payload = uptimely_plan.to_dict(_sample_plan())
    payload["plan_version"] = 6
    for invocation in payload["invocations"]:
        invocation["dataset_id"] = invocation.pop("profile_id")

    with pytest.raises(ValueError, match=r"Unsupported plan version: 6.*Recompile"):
        uptimely_plan.from_dict(payload)
    with pytest.raises(ValueError, match=r"Unsupported plan version: 6.*Recompile"):
        uptimely_plan.ExecutionPlan.model_validate(payload)


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
                    copy.replace(plan.invocations[0], dependency_ids=["unknown-invocation"]),
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
            copy.replace(plan, **changes)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("entrypoint", None, "must declare an entrypoint"),
        ("entrypoint", "", "must declare an entrypoint"),
    ],
)
def test_plan_rejects_invalid_invocation_metadata(field: str, value: object, message: str) -> None:
    payload = uptimely_plan.to_dict(_sample_plan())
    payload["invocations"][1][field] = value
    with pytest.raises(ValueError, match=message):
        uptimely_plan.from_dict(payload)


def test_plan_preserves_runtime_contract_fields() -> None:
    payload = uptimely_plan.to_dict(_sample_plan())
    payload["invocations"][1]["row_count_relation"] = "same"

    plan = uptimely_plan.from_dict(payload)

    assert plan.invocations[1].row_count_relation == "same"
