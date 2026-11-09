import collections.abc
import copy
import json

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
                operator_kind="read",
                entrypoint="example.functions:load",
                function_id="load",
                operator_id="read_pressure",
                profile_id="pump_profile",
                arguments={"dataset": {"type": "literal", "value": "pump_profile"}},
                dependency_ids=[],
                target_grain_keys=["plant", "pump"],
                fragment_identifiers=["plant", "pump"],
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
                operator_kind="collapse",
                entrypoint="example.functions:maximum",
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
                operator_kind="write",
                entrypoint="example.functions:save",
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


def test_plan_round_trip_preserves_operator_kind_metadata() -> None:
    plan = _sample_plan()

    payload = uptimely_plan.to_dict(plan)
    restored = uptimely_plan.from_dict(payload)

    assert restored == plan
    assert restored.invocations[1].function_id == "maximum"
    assert not hasattr(restored.invocations[1], "source")
    assert all("source" not in invocation for invocation in payload["invocations"])
    assert restored.invocations[1].entrypoint == "example.functions:maximum"
    assert restored.invocations[1].profile_id == "pump_profile"
    assert restored.invocations[1].operator_id == "pressure_by_pump"
    assert restored.invocations[0].function_id == "load"
    assert restored.invocations[0].operator_id == "read_pressure"
    assert restored.invocations[0].profile_id == "pump_profile"
    assert restored.invocations[0].id_columns == ["plant", "pump"]
    assert restored.invocations[0].output_types == {"pressure": "float"}
    assert restored.invocations[0].column_types == {
        "plant": "string",
        "pump": "string",
        "pressure": "float",
    }
    assert restored.invocations[0].argument_types == {"dataset": "dataframe"}
    assert all("profile_id" in invocation for invocation in payload["invocations"])
    assert all("dataset_id" not in invocation for invocation in payload["invocations"])
    assert all(not hasattr(invocation, "dataset_id") for invocation in restored.invocations)


def test_plan_round_trip_preserves_expansion_identifier_columns() -> None:
    original = _sample_plan()
    invocation = original.invocations[1].__replace__(
        operator_kind="expand", fragment_identifiers=["series"]
    )
    plan = original.__replace__(
        invocations=[original.invocations[0], invocation, original.invocations[2]]
    )

    restored = uptimely_plan.from_dict(uptimely_plan.to_dict(plan))

    assert restored == plan
    assert restored.invocations[1].identifier_columns == ["series"]


def test_plan_requires_fragment_identifier_metadata() -> None:
    payload = uptimely_plan.to_dict(_sample_plan())
    for invocation in payload["invocations"]:
        invocation.pop("fragment_identifiers")

    with pytest.raises(ValueError, match="missing runtime metadata: fragment_identifiers"):
        uptimely_plan.from_dict(payload)


def test_plan_round_trip_preserves_read_identifier_columns() -> None:
    original = _sample_plan()
    reader = original.invocations[0].__replace__(fragment_identifiers=["series", "category"])
    plan = original.__replace__(invocations=[reader, *original.invocations[1:]])

    restored = uptimely_plan.from_dict(uptimely_plan.to_dict(plan))

    assert restored == plan
    assert restored.invocations[0].identifier_columns == ["series", "category"]


@pytest.mark.parametrize("include_profile_id", [False, True])
def test_invocation_rejects_legacy_dataset_id_without_an_alias(
    include_profile_id: bool,
) -> None:
    payload = uptimely_plan.to_dict(_sample_plan())
    invocation = payload["invocations"][0]
    invocation["dataset_id"] = invocation["profile_id"]
    if not include_profile_id:
        del invocation["profile_id"]

    with pytest.raises(ValueError, match=r"dataset_id\n\s+Extra inputs are not permitted"):
        uptimely_plan.from_dict(payload)
    with pytest.raises(ValueError, match=r"dataset_id\n\s+Extra inputs are not permitted"):
        uptimely_plan.Invocation.model_validate(invocation)


@pytest.mark.parametrize(
    "field",
    [
        "target_grain_keys",
        "fragment_identifiers",
        "output_types",
        "produces_features",
        "is_sink",
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
    del payload["invocations"][0][field]

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
        [invocation.function_id for invocation in stage] for stage in plan.execution_stages
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
    assert payload["plan_version"] == 10
    assert "phase" not in payload["invocations"][0]
    assert not hasattr(plan.invocations[0], "phase")
    assert {"function_id", "operator_id"} <= set(payload["invocations"][0])
    assert "operator_kind" in payload["invocations"][0]
    assert payload["invocations"][0]["role"] == "compute"
    assert payload["invocations"][0]["result"] == "target"
    assert "operation" not in payload["invocations"][0]
    assert "output" not in payload["invocations"][0]
    assert payload["invocations"][0]["return_type"] == "DataFrame"
    assert payload["invocations"][0]["package"] == {
        "distribution": "example-package",
        "version": "1.0",
    }


def test_plan_json_helpers_round_trip(tmp_path) -> None:
    plan = _sample_plan()
    destination = tmp_path / "plan.json"

    uptimely_plan.export_json(plan, destination)
    payload = json.loads(destination.read_text(encoding="utf-8"))
    recreated = uptimely_plan.from_json(destination)

    assert payload["invocations"][0]["operator_kind"] == "read"
    assert recreated == plan
    assert recreated.invocations[0].id == "opaque-read"


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
        ValueError, match=r"Unsupported plan version: 1\. Supported version is 10\."
    ):
        uptimely_plan.from_dict(payload)


@pytest.mark.parametrize("version", [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, "10", "unsupported", None, True])
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


def test_plan_does_not_infer_runtime_contract_from_operator_kind() -> None:
    payload = uptimely_plan.to_dict(_sample_plan())
    payload["invocations"][1]["operator_kind"] = "expand"
    payload["invocations"][1]["row_count_relation"] = "same"

    plan = uptimely_plan.from_dict(payload)

    assert plan.invocations[1].operator_kind == "expand"
    assert plan.invocations[1].row_count_relation == "same"


class _CountingInvocations(list[uptimely_plan.Invocation]):
    traversals = 0

    def __iter__(self) -> collections.abc.Iterator[uptimely_plan.Invocation]:
        self.traversals += 1
        return super().__iter__()


def test_plan_cached_views_are_independent() -> None:
    original = _sample_plan()
    counted = _CountingInvocations(original.invocations)
    plan = uptimely_plan.ExecutionPlan.model_construct(
        plan_version=original.plan_version,
        required_backend=original.required_backend,
        invocations=counted,
        stages=original.stages,
    )
    counted.traversals = 0

    for _ in range(3):
        assert list(plan.invocations_by_id) == ["opaque-read", "opaque-collapse", "opaque-write"]
        assert plan.invocations_by_id["opaque-read"] is plan.invocations[0]
        assert plan.function_ids == {"load", "maximum", "save"}
        assert plan.profile_ids == {"pump_profile"}
        assert plan.arguments["opaque-read"] is plan.invocations[0].arguments
        assert plan.features["maximum"] == [plan.invocations[1]]
        assert plan.calculated_features == set()
        assert list(plan.entrypoints) == [
            "example.functions:load",
            "example.functions:maximum",
            "example.functions:save",
        ]
        assert plan.invocations_by_kind["collapse"] == [plan.invocations[1]]
        assert plan.count_per_kind == {"collapse": 1, "read": 1, "write": 1}
        assert list(plan.count_per_kind) == ["collapse", "read", "write"]
        assert plan.execution_stages == [[invocation] for invocation in original.invocations]
        assert plan.execution_invocations == original.invocations

    assert counted.traversals > 1
    assert plan.execution_stages is plan.execution_stages
    assert plan.execution_invocations is plan.execution_invocations
    assert plan.count_per_kind is plan.count_per_kind
    assert uptimely_plan.to_dict(plan) == uptimely_plan.to_dict(original)
    assert uptimely_plan.to_dict(plan) == uptimely_plan.to_dict(original)


def test_plan_keeps_signature_and_package_metadata_on_invocations() -> None:
    original = _sample_plan()
    invocation = original.invocations[0]
    assert invocation.return_type == "DataFrame"
    assert invocation.package is not None
    assert invocation.package.distribution == "example-package"
    assert not hasattr(original, "entrypoints_by_id")
    assert not hasattr(original, "entrypoint_packages")


def test_plan_rejects_function_ids_with_multiple_entrypoints() -> None:
    original = _sample_plan()
    conflicting = copy.replace(
        original.invocations[1],
        function_id=original.invocations[0].function_id,
        entrypoint="other.functions:load",
    )

    with pytest.raises(ValueError, match="assigns function 'load' to multiple entrypoints"):
        copy.replace(
            original,
            invocations=[original.invocations[0], conflicting, *original.invocations[2:]],
        )


def test_plan_rejects_conflicting_return_types_for_function() -> None:
    original = _sample_plan()
    conflicting = copy.replace(
        original.invocations[1],
        function_id=original.invocations[0].function_id,
        entrypoint=original.invocations[0].entrypoint,
        return_type="int",
        package=original.invocations[0].package,
    )

    with pytest.raises(ValueError, match="conflicting return annotations for function 'load'"):
        copy.replace(
            original,
            invocations=[original.invocations[0], conflicting, *original.invocations[2:]],
        )


def test_plan_replacement_does_not_retain_stale_indexes() -> None:
    plan = _sample_plan()
    original_index = plan.invocations_by_id
    original_execution = plan.execution_invocations
    original_features = plan.features
    replacement = copy.replace(plan.invocations[1], output_features=["changed"])
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


def test_plan_rejects_unsupported_operator_kind() -> None:
    payload = uptimely_plan.to_dict(_sample_plan())
    payload["invocations"][0]["operator_kind"] = "unsupported"
    with pytest.raises(ValueError):
        uptimely_plan.from_dict(payload)


def test_execution_invocations_follow_stages_not_declaration_order() -> None:
    original = _sample_plan()
    plan = copy.replace(original, invocations=list(reversed(original.invocations)))
    assert plan.invocations != original.invocations
    assert plan.execution_invocations == original.invocations
    assert uptimely_plan.to_dict(plan)["invocations"][0]["id"] == "opaque-write"

    independent = [
        copy.replace(invocation, dependency_ids=[]) for invocation in original.invocations
    ]
    grouped = copy.replace(
        original,
        invocations=independent,
        stages=[["opaque-write", "opaque-read"], [], ["opaque-collapse"]],
    )
    assert [invocation.id for invocation in grouped.execution_invocations] == [
        "opaque-write",
        "opaque-read",
        "opaque-collapse",
    ]
    empty = copy.replace(
        original,
        invocations=[],
        stages=[],
    )
    assert empty.execution_invocations == []
    assert empty.count_per_kind == {}


def test_count_per_kind_rebuilt_on_plan_replacement() -> None:
    plan = _sample_plan()
    previous = plan.count_per_kind
    plan.invocations[0] = copy.replace(plan.invocations[0], operator_kind="write")
    assert plan.count_per_kind is previous
    plan = copy.replace(plan)
    assert plan.count_per_kind == {"collapse": 1, "write": 2}
    assert plan.count_per_kind is not previous
