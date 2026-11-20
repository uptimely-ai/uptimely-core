import collections.abc
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
        assert plan.calculated_features == {"plant", "pump", "maximum"}
        assert list(plan.entrypoints) == [
            "example.src:load",
            "example.src:maximum",
            "example.src:save",
        ]
        assert plan.invocations_by_role["compute"] == plan.invocations
        assert plan.count_per_role == {"compute": 3}
        assert list(plan.count_per_role) == ["compute"]
        assert plan.execution_stages == [[invocation] for invocation in original.invocations]
        assert plan.execution_invocations == original.invocations

    assert counted.traversals > 1
    assert plan.execution_stages is plan.execution_stages
    assert plan.execution_invocations is plan.execution_invocations
    assert plan.count_per_role is plan.count_per_role
    assert uptimely_plan.to_dict(plan) == uptimely_plan.to_dict(original)
    assert uptimely_plan.to_dict(plan) == uptimely_plan.to_dict(original)


def test_plan_keeps_signature_and_package_metadata_on_invocations() -> None:
    original = _sample_plan()
    invocation = original.invocations[0]
    assert invocation.return_type == "DataFrame"
    assert invocation.package is not None
    assert invocation.package.distribution == "example-package"


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
    assert empty.count_per_role == {}


def test_count_per_role_rebuilt_on_plan_replacement() -> None:
    plan = _sample_plan()
    previous = plan.count_per_role
    plan.invocations[0] = copy.replace(
        plan.invocations[0],
        result="fragment",
        fragment_dimensions="target",
    )
    plan.invocations[1] = copy.replace(
        plan.invocations[1],
        role="merge",
        operator_id="read_pressure",
    )
    assert plan.count_per_role is previous
    plan = copy.replace(plan)
    assert plan.count_per_role == {"compute": 2, "merge": 1}
    assert plan.count_per_role is not previous
