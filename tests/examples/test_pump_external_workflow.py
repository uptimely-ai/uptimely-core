"""Run the pump example's uncontrolled workflow through a saved build."""

import json
import pathlib

import polars as pl
import pytest
from examples.pump_analytics.functions import external_workflow
from support import execution as execution_support

from uptimely import plan as plan_module
from uptimely import project


@pytest.mark.parametrize("dataset_lazy", [False, True])
@pytest.mark.parametrize("fragment_lazy", [False, True])
def test_custom_pump_merge_full_joins_on_dataset_keys(
    dataset_lazy: bool, fragment_lazy: bool
) -> None:
    dataset: pl.DataFrame | pl.LazyFrame = pl.DataFrame(
        {"pump_id": ["PUMP-101", "PUMP-201"], "bearing_temperature_max": [60.0, 70.0]}
    )
    fragment: pl.DataFrame | pl.LazyFrame = pl.DataFrame(
        {"pump_id": ["PUMP-201", "PUMP-301"], "measurement": [8.0, 9.0]}
    )
    if dataset_lazy:
        dataset = dataset.lazy()
    if fragment_lazy:
        fragment = fragment.lazy()

    result = external_workflow.merge_pump_inputs(dataset, fragment, ["pump_id"])
    if isinstance(result, pl.LazyFrame):
        result = result.collect()

    assert result.sort("pump_id").rows() == [
        ("PUMP-101", 60.0, None),
        ("PUMP-201", 70.0, 8.0),
        ("PUMP-301", None, 9.0),
    ]


def test_pump_external_workflow_declares_ratio_output_without_materializing_it(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    pump_bundle: project.BuildBundle,
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    """The declared boundary runs while the function owns internal I/O."""
    bundle = pump_bundle
    spec_definition = bundle.spec_definition
    plan_path = tmp_path / "execution_plan.json"
    plan_module.export_json(bundle.execution_plan, plan_path)
    saved_plan = plan_module.from_json(plan_path)
    output_path = tmp_path / "pump_external_workflow_results.csv"
    monkeypatch.setattr(external_workflow, "OUTPUT_PATH", output_path)
    parameters = json.loads(
        (bundle.project_root / "config" / "config.json").read_text(encoding="utf-8")
    )["params"]

    result = engine_for_plan(
        saved_plan,
        parameters=parameters,
        project_root=bundle.project_root,
        spec_definition=spec_definition,
    ).run()

    escape = next(
        invocation
        for invocation in saved_plan.invocations
        if invocation.function_id == "process_pump_external_workflow"
    )
    assert escape.operator_kind == "escape"
    assert escape.input_features == ["measurement", "reference_value"]
    assert escape.output_features == ["ratio"]
    assert result.invocation_statuses[escape.id] == "succeeded"
    assert all(status == "succeeded" for status in result.invocation_statuses.values())
    assert result.failures == {}
    assert len(result.datasets) == 8
    dataset = result.datasets["pump"]
    assert {
        "bearing_temperature_max",
        "measurement",
        "reference_value",
    } <= set(dataset.collect_schema().names())
    assert "ratio" in spec_definition.profiles["pump"].features
    assert "ratio" not in dataset.collect_schema().names()
    assert ("pump", "ratio") not in result.calculated_outputs
    assert pl.read_csv(output_path).select("pump_id", "ratio").rows() == [
        ("PUMP-101", 0.75),
        ("PUMP-201", 1.0),
    ]
