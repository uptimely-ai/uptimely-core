"""Run the documented escape workflow example through a saved execution plan."""

import pathlib

import polars as pl
import pytest
from conftest import engine_for_plan
from examples.escape_operation.functions import workflow

from uptimely import compiler, spec
from uptimely import execution_plan as plan_module

EXAMPLE_ROOT = pathlib.Path(__file__).parents[2] / "examples" / "escape_operation"
SPEC_PATH = EXAMPLE_ROOT / "spec" / "spec.json"


def test_escape_example_reads_calculates_and_writes_without_materializing_outputs(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The declared boundary compiles while the function owns internal I/O."""
    spec_definition = spec.load_spec(SPEC_PATH)
    compiled = compiler.Compiler().compile(spec_definition)
    plan_path = tmp_path / "execution_plan.json"
    plan_module.export_json(compiled, plan_path)
    saved_plan = plan_module.from_json(plan_path)
    output_path = tmp_path / "workflow_results.csv"
    monkeypatch.setattr(workflow, "OUTPUT_PATH", output_path)

    result = engine_for_plan(
        saved_plan,
        project_root=EXAMPLE_ROOT,
        spec_definition=spec_definition,
    ).run()

    escape = next(callable for callable in saved_plan.callables if callable.operation == "escape")
    assert escape.operation == "escape"
    assert escape.input_features == ["measurement", "reference_value"]
    assert escape.output_features == ["ratio"]
    assert result.callable_statuses[escape.id] == "succeeded"
    assert all(status == "succeeded" for status in result.callable_statuses.values())
    assert result.failures == {}
    assert len(result.datasets) == 1
    assert "ratio" not in result.datasets["external_workflow"].columns
    assert result.calculated_outputs == {}
    assert pl.read_csv(output_path).rows() == [("P-01", 0.75), ("P-02", 1.0)]
