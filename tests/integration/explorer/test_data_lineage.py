"""Tests for the typed data-lineage presentation model."""

import pytest

from uptimely import plan as execution_plan
from uptimely import spec
from uptimely.explorer.sections import data_lineage
from uptimely.spec import function_kinds as functions


@pytest.mark.parametrize(
    ("kind", "source_dimensions", "target_dimensions", "row_counts"),
    [
        ("collapse", ["id", "time"], ["id"], (3, 1)),
        ("expand", ["id"], ["id", "time"], (1, 3)),
        ("conform", ["id"], ["id"], (3, 3)),
    ],
)
def test_transfer_tables_preserve_source_grain_and_shared_keys(
    kind: functions.FunctionKindId,
    source_dimensions: list[str],
    target_dimensions: list[str],
    row_counts: tuple[int, int],
) -> None:
    definition = spec.Spec.model_validate(
        {
            "dimensions": {
                dimension: {"resolutions": {dimension: {"key": dimension, "type": "integer"}}}
                for dimension in ("id", "time")
            },
            "profiles": {
                name: {
                    "grain": [
                        {"dimension": dimension, "resolution": dimension}
                        for dimension in dimensions
                    ],
                    "features": {feature: {"type": "float"}},
                }
                for name, dimensions, feature in (
                    ("source", source_dimensions, "input_value"),
                    ("target", target_dimensions, "result"),
                )
            },
        }
    )
    invocation = execution_plan.Invocation(
        id="transfer",
        function_kind=kind,
        entrypoint="example:transfer",
        function_id="transfer",
        operator_id="transfer_source-values",
        profile_id="target",
        input_features=["input_value"],
        output_features=["result"],
    )
    plan = execution_plan.ExecutionPlan(
        plan_version=execution_plan.PLAN_VERSION,
        required_backend="polars",
        resources={},
        invocations=[invocation],
        stages=[["transfer"]],
    )

    step = data_lineage.build_context(definition, plan)["stages"][0][0]
    source = step.input_tables[0]

    assert step.operator == "Transfer Source Values"
    assert source.dataset == "source"
    assert [key.name for key in source.keys] == source_dimensions
    assert source.join_dimensions == ["id"]
    assert (source.row_count, step.row_count) == row_counts


def test_main_table_tracks_only_materialized_outputs(pump_bundle) -> None:
    accumulated: dict[str | None, list[str]] = {}
    steps = [
        step
        for stage in data_lineage._build_stages(
            pump_bundle.spec_definition, pump_bundle.execution_plan
        )
        for step in stage
    ]

    for step in steps:
        expected = accumulated.setdefault(step.dataset, [])
        current_outputs = [
            column.name
            for column in step.columns
            if column.role == "Output" and not step.kind.is_effect
        ]
        expected[:] = [name for name in expected if name not in current_outputs]
        expected.extend(current_outputs)
        assert [column.name for column in step.main_columns] == expected
        assert [column.name for column in step.main_columns if column.role == "Output"] == (
            current_outputs
        )
        for source in step.input_tables:
            assert source.dataset != step.dataset


def test_animation_stages_match_compiled_execution_order(pump_bundle) -> None:
    stages = data_lineage._build_stages(pump_bundle.spec_definition, pump_bundle.execution_plan)

    assert [len(stage) for stage in stages] == [
        len(stage) for stage in pump_bundle.execution_plan.execution_stages
    ]
    for animation_stage, plan_stage in zip(
        stages, pump_bundle.execution_plan.execution_stages, strict=True
    ):
        assert {step.invocation_id for step in animation_stage} == {
            invocation.id for invocation in plan_stage
        }
    for stage in stages:
        for step in stage:
            if step.kind.id == "merge":
                assert all(column.role == "Dimension" for column in step.columns)
            else:
                assert step.columns
