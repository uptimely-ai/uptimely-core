"""Run the pump example's uncontrolled workflow through a saved build."""

import pathlib
import tomllib

import polars as pl
import pump_merge as merge
import pytest
from support import examples as example_support
from support import execution as execution_support

from uptimely import application
from uptimely import plan as plan_module


@pytest.mark.parametrize("dataset_lazy", [False, True])
@pytest.mark.parametrize("fragment_lazy", [False, True])
def test_custom_pump_merge_full_joins_on_dataset_identifiers(
    dataset_lazy: bool, fragment_lazy: bool
) -> None:
    dataset: pl.DataFrame | pl.LazyFrame = pl.DataFrame(
        {"pump_id": ["CWP-101", "CWP-201"], "bearing_temperature_max": [60.0, 70.0]}
    )
    fragment: pl.DataFrame | pl.LazyFrame = pl.DataFrame(
        {"pump_id": ["CWP-201", "CWP-301"], "measurement": [8.0, 9.0]}
    )
    if dataset_lazy:
        dataset = dataset.lazy()
    if fragment_lazy:
        fragment = fragment.lazy()

    result = merge.merge_pump_inputs(dataset, fragment, ["pump_id"])
    if isinstance(result, pl.LazyFrame):
        result = result.collect()

    assert result.sort("pump_id").rows() == [
        ("CWP-101", 60.0, None),
        ("CWP-201", 70.0, 8.0),
        ("CWP-301", None, 9.0),
    ]


def test_pump_external_workflow_runs_with_its_own_paths(
    tmp_path: pathlib.Path,
    example_project_factory: example_support.ProjectFactory,
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    """The declared boundary runs while the function owns internal I/O."""
    root = example_project_factory(tmp_path / "example")
    bundle = application.load_build_bundle(root)
    spec_definition = bundle.spec_definition
    plan_path = tmp_path / "execution_plan.json"
    plan_module.export_json(bundle.execution_plan, plan_path)
    saved_plan = plan_module.from_json(plan_path)
    output_path = root / "data" / "output" / "pump_external_workflow_results.csv"
    configuration = tomllib.loads(
        (bundle.project_root / "uptimely.toml").read_text(encoding="utf-8")
    )
    parameters = configuration["params"]
    paths: dict[str, str] = {}
    for name, value in configuration["paths"].items():
        configured = pathlib.Path(value)
        paths[name] = str(
            configured if configured.is_absolute() else bundle.project_root / configured
        )
    result = engine_for_plan(
        saved_plan,
        parameters=parameters,
        project_root=bundle.project_root,
        spec_definition=spec_definition,
        paths=paths,
    ).run(validate=True)

    profile_output_paths = [
        pathlib.Path(paths[name]) for name in configuration["paths"] if name.endswith("_output")
    ]
    workflow = next(
        invocation
        for invocation in saved_plan.invocations
        if invocation.function_id == "process_pump_external_workflow"
    )
    assert workflow.is_workflow
    assert workflow.arguments == {}
    assert workflow.input_features == ["measurement", "reference_value"]
    assert workflow.output_features == []
    assert result.invocation_statuses[workflow.id] == "succeeded"
    assert all(status == "succeeded" for status in result.invocation_statuses.values())
    assert result.failures == {}
    assert len(result.datasets) == 10
    assert all(path.is_file() for path in profile_output_paths)
    dataset = result.datasets["pump"]
    assert {
        "bearing_temperature_max",
        "measurement",
        "reference_value",
    } <= set(dataset.collect_schema().names())
    assert pl.read_csv(output_path).select("pump_id", "ratio").rows() == [
        ("CWP-101", 0.75),
        ("CWP-201", 1.0),
    ]


@pytest.mark.parametrize("fails", [False, True])
def test_selected_workflow_ignores_returns_and_reports_failures(
    tmp_path: pathlib.Path,
    example_project_factory: example_support.ProjectFactory,
    fails: bool,
) -> None:
    root = example_project_factory(tmp_path / "example", features=("measurement",))
    source = root / "src" / "pump_io.py"
    statement = "raise RuntimeError('workflow failed')" if fails else "return {'ignored': True}"
    source.write_text(
        source.read_text(encoding="utf-8")
        + f"\ndef process_pump_external_workflow():\n    {statement}\n",
        encoding="utf-8",
    )
    app = application.Uptimely(root)
    bundle = application.load_build_bundle(root)
    workflow = next(item for item in bundle.execution_plan.invocations if item.is_workflow)
    result = app.create_engine(bundle).run()
    assert result.invocation_statuses[workflow.id] == ("failed" if fails else "succeeded")
    if fails:
        assert "workflow failed" in result.failures[workflow.id]
    else:
        assert result.failures == {}
