import json
import pathlib
import sys

import polars as pl
import pytest
from conftest import EXAMPLES_ROOT, copy_example_project, engine_for_plan, example_bundle
from examples.pump_analytics.functions import analytics

from uptimely import compiler
from uptimely import spec as spec_module
from uptimely.cli import cli
from uptimely.engine import dataframe as dataframe_module
from uptimely.engine import state as state_module

SPEC_PATH = EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json"
ENGINE_CONFIG_PATH = EXAMPLES_ROOT / "pump_analytics/config/engine.json"


def _engine_bind() -> dict[str, object]:
    engine_config = json.loads(ENGINE_CONFIG_PATH.read_text(encoding="utf-8"))
    return engine_config["bind"]


def _execution_plan() -> compiler.ExecutionPlan:
    return example_bundle().execution_plan


def _execution_spec() -> spec_module.Spec:
    return spec_module.load_spec(SPEC_PATH)


def _copy_pump_project(
    tmp_path: pathlib.Path, features: tuple[str, ...] | None = None
) -> pathlib.Path:
    project_root = tmp_path / "examples" / "pump_analytics"
    copy_example_project(project_root, features=features)
    (project_root.parent / "__init__.py").write_text("", encoding="utf-8")
    return project_root


def test_engine_returns_calculated_features_without_writing_output() -> None:
    engine = engine_for_plan(_execution_plan(), _engine_bind(), spec_definition=_execution_spec())

    result = engine.run()

    assert not result.failures
    assert sorted({feature for _, feature in result.calculated_outputs}) == [
        "bearing_temperature_delta",
        "converged",
        "energy_cost_score",
        "health_signal_normalized",
        "operating_point_recommendation",
        "pressure_flow_efficiency",
        "pump_health_score",
        "recommended_discharge_pressure",
        "recommended_flow_rate",
        "vibration_delta",
    ]
    assert isinstance(
        result.calculated_outputs[("pump_dataset", "health_signal_normalized")],
        pl.LazyFrame,
    )
    pump_frame = result.datasets["pump_dataset"].collect()
    assert pump_frame.select("pump", "bearing_temperature_max", "health_signal_normalized").sort(
        "pump"
    ).rows() == [
        ("PUMP-101", 68.7, 1.0),
        ("PUMP-201", 64.5, -1.0),
    ]
    telemetry_frame = result.datasets["pump_telemetry_dataset"].collect()
    assert "health_signal_normalized" not in telemetry_frame.columns
    telemetry_frame = telemetry_frame.sort("pump", "timestamp")
    assert telemetry_frame["pump"].to_list() == ["PUMP-101", "PUMP-101", "PUMP-201"]
    efficiency = [5.3 * 118.0 / (36 * 17.9), 5.4 * 119.5 / (36 * 18.1), 4.1 * 83.0 / (36 * 11.7)]
    assert telemetry_frame["pressure_flow_efficiency"].to_list() == pytest.approx(efficiency)
    assert telemetry_frame["bearing_temperature_delta"].to_list() == [None, 0.5, None]
    assert telemetry_frame["vibration_delta"].to_list() == pytest.approx([None, 0.1, None])
    assert telemetry_frame["pump_health_score"].to_list() == pytest.approx(
        [None, efficiency[1] - 0.05 - 0.05, None]
    )
    assert telemetry_frame["recommended_flow_rate"].to_list() == [118.0, 119.5, 83.0]
    assert telemetry_frame["recommended_discharge_pressure"].to_list() == [5.3, 5.4, 4.1]
    assert telemetry_frame["energy_cost_score"].to_list() == pytest.approx(
        [17.9 / 118.0, 18.1 / 119.5, 11.7 / 83.0]
    )
    assert telemetry_frame["converged"].to_list() == [True, True, True]
    recommendations = telemetry_frame["operating_point_recommendation"].to_list()
    for recommendation, flow, pressure, cost in zip(
        recommendations,
        [118.0, 119.5, 83.0],
        [5.3, 5.4, 4.1],
        [17.9 / 118.0, 18.1 / 119.5, 11.7 / 83.0],
        strict=True,
    ):
        assert recommendation == pytest.approx(
            {
                "recommended_flow_rate": flow,
                "recommended_discharge_pressure": pressure,
                "energy_cost_score": cost,
                "converged": True,
            }
        )


def test_engine_cli_reports_processed_datasets(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project_root = _copy_pump_project(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "uptimely",
            "engine",
            "run",
            "--project-root",
            str(project_root),
            "--verbose",
            "--preview",
            "1",
        ],
    )
    cli.main()

    output = capsys.readouterr().out
    assert "Scope: all features" in output
    assert "- Dataset: pump_dataset - 5 features" in output
    assert "Dataset: pump_dataset\n" in output
    assert "Dataset: pump_telemetry_dataset\n" in output
    assert output.index("- Dataset: pump_dataset - 5 features") < output.index(
        "Dataset: pump_dataset\n"
    )
    assert "shape:" not in output


def test_engine_cli_reports_scoped_saved_build(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project_root = _copy_pump_project(tmp_path, features=("health_signal_normalized",))
    monkeypatch.setattr(
        sys,
        "argv",
        ["uptimely", "engine", "run", "--project-root", str(project_root), "--verbose"],
    )

    cli.main()

    output = capsys.readouterr().out
    assert "Scope: selected features: health_signal_normalized" in output
    assert "- Dataset: pump_dataset - 5 features" in output


def test_simple_analytics_engine_cli_executes_saved_build(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project_root = EXAMPLES_ROOT / "simple_analytics"
    monkeypatch.setattr(
        sys,
        "argv",
        ["uptimely", "engine", "run", "--project-root", str(project_root), "--verbose"],
    )

    cli.main()

    output = capsys.readouterr().out
    assert "Scope: all features" in output
    assert "- Dataset: my_beautiful_dataset - 5 features" in output
    result_lines = [line for line in output.splitlines() if line.startswith("[")]
    assert len(result_lines) == 1
    assert json.loads(result_lines[0]) == [
        {"column_3": 3, "column_4": True},
        {"column_3": 7, "column_4": True},
    ]


def test_engine_rejects_unknown_runtime_namespace() -> None:
    engine = engine_for_plan(_execution_plan(), {}, spec_definition=_execution_spec())

    result = engine.run()

    assert any(
        "Unknown runtime namespace: storage" in message for message in result.failures.values()
    )


def test_engine_rejects_unknown_runtime_object() -> None:
    engine = engine_for_plan(_execution_plan(), {"storage": {}}, spec_definition=_execution_spec())

    result = engine.run()

    assert any(
        "Unknown storage object: telemetry_source" in message
        for message in result.failures.values()
    )


def test_engine_rejects_unknown_runtime_attribute() -> None:
    engine = engine_for_plan(
        _execution_plan(),
        {"storage": {"telemetry_source": {}}},
        spec_definition=_execution_spec(),
    )

    result = engine.run()

    assert any(
        "storage object telemetry_source has no attribute: path" in message
        for message in result.failures.values()
    )


def test_engine_merges_fragments_by_entity_dimensions() -> None:
    engine = engine_for_plan(_execution_plan(), spec_definition=_execution_spec())
    dataframe = dataframe_module.DataFrameExecution(
        engine.backend, engine.spec_definition, state_module.RuntimeState()
    )
    existing = pl.LazyFrame(
        {
            "plant": ["PLANT-01", "PLANT-01"],
            "production_line": ["LINE-A", "LINE-B"],
            "pump": ["PUMP-101", "PUMP-201"],
            "existing": [1, 2],
        }
    )
    fragment = pl.LazyFrame(
        {
            "plant": ["PLANT-01", "PLANT-01"],
            "production_line": ["LINE-B", "LINE-A"],
            "pump": ["PUMP-201", "PUMP-101"],
            "new": [20, 10],
        }
    )

    operation = next(
        operation
        for operation in engine.plan.invocations
        if operation.entity_id == "pump" and operation.dataset_id == "pump_dataset"
    )
    dimensions = engine.spec_definition.entities[operation.entity_id].dimension_ids
    merged = dataframe.merge_fragment(existing, fragment, dimensions).collect()

    assert merged.select("pump", "existing", "new").sort("pump").rows() == [
        ("PUMP-101", 1, 10),
        ("PUMP-201", 2, 20),
    ]


@pytest.mark.parametrize(("existing_lazy", "fragment_lazy"), [(True, False), (False, True)])
def test_engine_assembly_accepts_mixed_eager_and_lazy_frames(
    existing_lazy: bool, fragment_lazy: bool
) -> None:
    engine = engine_for_plan(_execution_plan(), spec_definition=_execution_spec())
    dataframe = dataframe_module.DataFrameExecution(
        engine.backend, engine.spec_definition, state_module.RuntimeState()
    )
    existing: pl.DataFrame | pl.LazyFrame = pl.DataFrame({"key": ["A"], "old": [1]})
    fragment: pl.DataFrame | pl.LazyFrame = pl.DataFrame({"key": ["B"], "new": [2]})
    if existing_lazy:
        existing = existing.lazy()
    if fragment_lazy:
        fragment = fragment.lazy()

    merged = dataframe.merge_fragment(existing, fragment, ["key"])

    assert isinstance(merged, pl.LazyFrame)
    assert merged.collect().sort("key").select("key", "old", "new").rows() == [
        ("A", 1, None),
        ("B", None, 2),
    ]


@pytest.mark.parametrize("lazy", [False, True])
@pytest.mark.parametrize(
    ("existing_keys", "fragment_keys", "expected_keys"),
    [
        ([None, "A"], [None, "B"], [None, "A", "B"]),
        (["A"], ["B"], ["A", "B"]),
    ],
)
def test_engine_assembly_preserves_partial_and_disjoint_keys(
    lazy: bool,
    existing_keys: list[str | None],
    fragment_keys: list[str | None],
    expected_keys: list[str | None],
) -> None:
    engine = engine_for_plan(_execution_plan(), spec_definition=_execution_spec())
    dataframe = dataframe_module.DataFrameExecution(
        engine.backend, engine.spec_definition, state_module.RuntimeState()
    )
    existing = pl.DataFrame({"key": existing_keys, "old": list(range(len(existing_keys)))})
    fragment = pl.DataFrame({"key": fragment_keys, "new": list(range(10, 10 + len(fragment_keys)))})
    if lazy:
        existing, fragment = existing.lazy(), fragment.lazy()

    merged = dataframe.merge_fragment(existing, fragment, ["key"])
    if isinstance(merged, pl.LazyFrame):
        merged = merged.collect()

    assert sorted(merged["key"].to_list(), key=lambda value: value or "") == sorted(
        expected_keys, key=lambda value: value or ""
    )
    if None in existing_keys:
        assert merged.filter(pl.col("key").is_null()).select("old", "new").row(0) == (0, 10)


@pytest.mark.parametrize("lazy", [False, True])
@pytest.mark.parametrize("duplicate_side", ["existing", "fragment"])
def test_engine_assembly_rejects_duplicate_keys_on_either_side(
    lazy: bool, duplicate_side: str
) -> None:
    engine = engine_for_plan(_execution_plan(), spec_definition=_execution_spec())
    dataframe = dataframe_module.DataFrameExecution(
        engine.backend, engine.spec_definition, state_module.RuntimeState()
    )
    existing = pl.DataFrame({"key": ["A", "A"], "old": [1, 2]})
    fragment = pl.DataFrame({"key": ["A"], "new": [3]})
    if duplicate_side == "fragment":
        existing = pl.DataFrame({"key": ["A"], "old": [1]})
        fragment = pl.DataFrame({"key": ["A", "A"], "new": [3, 4]})
    if lazy:
        existing, fragment = existing.lazy(), fragment.lazy()

    with pytest.raises(ValueError, match="duplicate dimension keys"):
        dataframe.merge_fragment(existing, fragment, ["key"])


@pytest.mark.parametrize("lazy", [False, True])
@pytest.mark.parametrize("invalid_column", ["key", "output", "missing"])
def test_engine_validates_required_fragment_columns_and_types(
    lazy: bool, invalid_column: str
) -> None:
    engine = engine_for_plan(_execution_plan(), spec_definition=_execution_spec())
    dataframe = dataframe_module.DataFrameExecution(
        engine.backend, engine.spec_definition, state_module.RuntimeState()
    )
    invocation = next(
        item
        for item in engine.plan.invocations
        if item.dataset_id == "pump_dataset" and item.operation == "collapse"
    )
    dimensions = engine.spec_definition.entities[invocation.entity_id].dimension_ids
    output = next(name for name in invocation.output_features if name not in dimensions)
    columns: dict[str, list[object]] = {name: [f"{name}-1"] for name in dimensions}
    columns[output] = ["wrong type" if invalid_column == "output" else 1.5]
    if invalid_column == "key":
        columns[dimensions[0]] = [1]
    if invalid_column == "missing":
        columns.pop(output)
    result: pl.DataFrame | pl.LazyFrame = pl.DataFrame(columns)
    if lazy:
        result = result.lazy()

    expected = {
        "key": f"Output column {dimensions[0]} has type",
        "output": f"Output column {output} has type",
        "missing": f"missing output columns: {output}",
    }[invalid_column]
    with pytest.raises(ValueError, match=expected):
        dataframe.validate_result(invocation, result, None, dimensions)


@pytest.mark.parametrize("lazy", [False, True])
def test_engine_assembly_rejects_feature_collisions(lazy: bool) -> None:
    engine = engine_for_plan(_execution_plan(), spec_definition=_execution_spec())
    dataframe = dataframe_module.DataFrameExecution(
        engine.backend, engine.spec_definition, state_module.RuntimeState()
    )
    invocation = next(
        item
        for item in engine.plan.invocations
        if item.dataset_id == "pump_dataset" and item.operation == "collapse"
    )
    dimensions = engine.spec_definition.entities[invocation.entity_id].dimension_ids
    output = next(name for name in invocation.output_features if name not in dimensions)
    keys = {name: [f"{name}-1"] for name in dimensions}
    result = pl.DataFrame({**keys, output: [1.5]})
    existing = pl.DataFrame({**keys, output: [2.5]})
    if lazy:
        result, existing = result.lazy(), existing.lazy()

    with pytest.raises(ValueError, match=f"overlap.*{output}"):
        dataframe.assemble_fragment(invocation, result, existing, None, dimensions)


@pytest.mark.parametrize(
    ("fragment", "message"),
    [
        (None, "must return a Polars DataFrame or LazyFrame"),
        (pl.LazyFrame({"pump": ["PUMP-101"]}), "missing dimension columns"),
        (
            pl.LazyFrame(
                {
                    "plant": ["PLANT-01", "PLANT-01"],
                    "production_line": ["LINE-A", "LINE-A"],
                    "pump": ["PUMP-101", "PUMP-101"],
                }
            ),
            "duplicate dimension keys",
        ),
    ],
)
def test_engine_rejects_invalid_fragments(fragment: object, message: str) -> None:
    engine = engine_for_plan(_execution_plan(), spec_definition=_execution_spec())
    dataframe = dataframe_module.DataFrameExecution(
        engine.backend, engine.spec_definition, state_module.RuntimeState()
    )
    operation = next(
        operation
        for operation in engine.plan.invocations
        if operation.entity_id == "pump" and operation.dataset_id == "pump_dataset"
    )

    with pytest.raises(ValueError, match=message):
        dataframe.validate_result(
            operation,
            fragment,
            None,
            engine.spec_definition.entities[operation.entity_id].dimension_ids,
        )


def test_engine_looks_up_datasets_by_project_wide_id() -> None:
    frame = pl.LazyFrame({"id": [1]})
    state = state_module.RuntimeState(datasets={"shared": frame})

    assert state.dataframe_by_id("shared") is frame
    assert state.dataframe_by_id("missing") is None


def test_example_deltas_are_partitioned_and_ordered() -> None:
    frame = pl.DataFrame(
        {
            "pump": ["PUMP-101", "PUMP-201", "PUMP-101", "PUMP-201"],
            "timestamp": [2, 2, 1, 1],
            "bearing_temperature": [11.5, 22.5, 10.0, 20.0],
            "vibration_rms": [1.2, 2.4, 1.0, 2.0],
        }
    )

    result = analytics.bearing_temperature_delta(
        frame.lazy(),
        "bearing_temperature",
        ["pump"],
        "timestamp",
        "temperature_delta",
    )
    result = (
        analytics.vibration_delta_from_previous(
            result,
            "vibration_rms",
            ["pump"],
            "timestamp",
            "vibration_delta",
        )
        .collect()
        .sort("pump", "timestamp")
    )

    assert result["pump"].to_list() == [
        "PUMP-101",
        "PUMP-101",
        "PUMP-201",
        "PUMP-201",
    ]
    assert result["temperature_delta"].null_count() == 2
    assert result["temperature_delta"].drop_nulls().to_list() == pytest.approx([1.5, 2.5])
    assert result["vibration_delta"].null_count() == 2
    assert result["vibration_delta"].drop_nulls().to_list() == pytest.approx([0.2, 0.4])


def test_engine_executes_requested_feature_and_its_dependencies(tmp_path: pathlib.Path) -> None:
    spec_definition = _execution_spec()
    plan = example_bundle(features=("health_signal_normalized",)).execution_plan
    engine = engine_for_plan(plan, _engine_bind(), spec_definition=spec_definition)
    assert [
        feature
        for stage in engine.plan.execution_stages
        for operation in stage
        if operation.operation == "vectorize"
        for feature in operation.output_features
    ] == [
        "health_signal_normalized",
    ]
    assert {
        operation.operation for stage in engine.plan.execution_stages for operation in stage
    } == {
        "read",
        "collapse",
        "vectorize",
    }

    result = engine.run()

    assert result.datasets["pump_dataset"].collect().height == 2
