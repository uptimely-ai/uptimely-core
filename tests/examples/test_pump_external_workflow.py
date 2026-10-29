"""Run the pump example's uncontrolled workflow through a saved build."""

import json
import pathlib

import polars as pl
import pytest
from examples.pump_analytics.functions import external_workflow
from support import execution as execution_support

from uptimely import execution_plan as plan_module
from uptimely import project


def test_pump_external_workflow_reads_calculates_and_writes_without_materializing_outputs(
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
    assert escape.function_kind == "escape"
    assert escape.input_features == ["measurement", "reference_value"]
    assert escape.output_features == ["ratio"]
    assert result.invocation_statuses[escape.id] == "succeeded"
    assert all(status == "succeeded" for status in result.invocation_statuses.values())
    assert result.failures == {}
    assert len(result.datasets) == 4
    dataset = result.datasets["pump_external_workflow_dataset"]
    assert "ratio" not in dataset.columns
    assert ("pump_external_workflow_dataset", "ratio") not in result.calculated_outputs
    assert pl.read_csv(output_path).select("pump", "ratio").rows() == [
        ("PUMP-101", 0.75),
        ("PUMP-201", 1.0),
    ]
