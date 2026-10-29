import json
import pathlib
import sys

import polars as pl
import pytest
from examples.pump_analytics.functions import analytics
from support import examples as example_support
from support import execution as execution_support

from uptimely import project
from uptimely.cli import cli
from uptimely.engine import dataframe as dataframe_module
from uptimely.engine import state as state_module


def _engine_parameters() -> dict[str, object]:
    path = example_support.EXAMPLES_ROOT / "pump_analytics/config/config.json"
    return json.loads(path.read_text(encoding="utf-8"))["params"]


def test_engine_returns_calculated_features_without_writing_output(
    pump_bundle: project.BuildBundle, engine_for_plan: execution_support.EngineFactory
) -> None:
    engine = engine_for_plan(
        pump_bundle.execution_plan,
        _engine_parameters(),
        spec_definition=pump_bundle.spec_definition,
    )

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
    assert telemetry_frame["operation_mode"].to_list() == [
        "low_speed",
        "high_speed",
        "low_speed",
    ]
    assert result.datasets["constants_dataset"].collect().to_dicts() == [
        {"gravity": 9.81, "room_temperature": 20.0}
    ]
    assert analytics.read_constants(
        str(example_support.EXAMPLES_ROOT / "pump_analytics/data/constants_dev.json")
    ).collect().to_dicts() == [{"gravity": 9.81, "room_temperature": 22.0}]
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
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    example_project_factory: example_support.ProjectFactory,
) -> None:
    project_root = example_project_factory(tmp_path / "examples" / "pump_analytics")
    (project_root.parent / "__init__.py").write_text("", encoding="utf-8")
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
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    example_project_factory: example_support.ProjectFactory,
) -> None:
    project_root = example_project_factory(
        tmp_path / "examples" / "pump_analytics", features=("health_signal_normalized",)
    )
    (project_root.parent / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        ["uptimely", "engine", "run", "--project-root", str(project_root), "--verbose"],
    )

    cli.main()

    output = capsys.readouterr().out
    assert "Scope: selected features: health_signal_normalized" in output
    assert "- Dataset: pump_dataset - 5 features" in output


def test_engine_rejects_missing_parameter(
    pump_bundle: project.BuildBundle, engine_for_plan: execution_support.EngineFactory
) -> None:
    engine = engine_for_plan(
        pump_bundle.execution_plan, {}, spec_definition=pump_bundle.spec_definition
    )

    result = engine.run()

    assert any(
        "Unresolved parameter: telemetry_source" in message for message in result.failures.values()
    )


def test_engine_rejects_unknown_parameter_name(
    pump_bundle: project.BuildBundle, engine_for_plan: execution_support.EngineFactory
) -> None:
    engine = engine_for_plan(
        pump_bundle.execution_plan,
        {"another_parameter": "value"},
        spec_definition=pump_bundle.spec_definition,
    )

    result = engine.run()

    assert any(
        "Unresolved parameter: telemetry_source" in message for message in result.failures.values()
    )


def test_engine_rejects_non_scalar_parameter_value(
    pump_bundle: project.BuildBundle, engine_for_plan: execution_support.EngineFactory
) -> None:
    with pytest.raises(ValueError, match="must be a JSON scalar"):
        engine_for_plan(
            pump_bundle.execution_plan,
            {"telemetry_source": {"path": "input.json"}},
            spec_definition=pump_bundle.spec_definition,
        )


def test_engine_merges_fragments_by_entity_dimensions(
    pump_bundle: project.BuildBundle, engine_for_plan: execution_support.EngineFactory
) -> None:
    engine = engine_for_plan(
        pump_bundle.execution_plan, spec_definition=pump_bundle.spec_definition
    )
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
    existing_lazy: bool,
    fragment_lazy: bool,
    pump_bundle: project.BuildBundle,
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    engine = engine_for_plan(
        pump_bundle.execution_plan, spec_definition=pump_bundle.spec_definition
    )
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
    pump_bundle: project.BuildBundle,
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    engine = engine_for_plan(
        pump_bundle.execution_plan, spec_definition=pump_bundle.spec_definition
    )
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
    lazy: bool,
    duplicate_side: str,
    pump_bundle: project.BuildBundle,
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    engine = engine_for_plan(
        pump_bundle.execution_plan, spec_definition=pump_bundle.spec_definition
    )
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
    lazy: bool,
    invalid_column: str,
    pump_bundle: project.BuildBundle,
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    engine = engine_for_plan(
        pump_bundle.execution_plan, spec_definition=pump_bundle.spec_definition
    )
    dataframe = dataframe_module.DataFrameExecution(
        engine.backend, engine.spec_definition, state_module.RuntimeState()
    )
    invocation = next(
        item
        for item in engine.plan.invocations
        if item.dataset_id == "pump_dataset" and item.function_kind == "collapse"
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
        dataframe.assemble_fragment(invocation, result, None, dimensions)


@pytest.mark.parametrize("lazy", [False, True])
def test_engine_assembly_rejects_feature_collisions(
    lazy: bool, pump_bundle: project.BuildBundle, engine_for_plan: execution_support.EngineFactory
) -> None:
    engine = engine_for_plan(
        pump_bundle.execution_plan, spec_definition=pump_bundle.spec_definition
    )
    dataframe = dataframe_module.DataFrameExecution(
        engine.backend, engine.spec_definition, state_module.RuntimeState()
    )
    invocation = next(
        item
        for item in engine.plan.invocations
        if item.dataset_id == "pump_dataset" and item.function_kind == "collapse"
    )
    dimensions = engine.spec_definition.entities[invocation.entity_id].dimension_ids
    output = next(name for name in invocation.output_features if name not in dimensions)
    keys = {name: [f"{name}-1"] for name in dimensions}
    result = pl.DataFrame({**keys, output: [1.5]})
    existing = pl.DataFrame({**keys, output: [2.5]})
    if lazy:
        result, existing = result.lazy(), existing.lazy()

    with pytest.raises(ValueError, match=f"overlap.*{output}"):
        dataframe.assemble_fragment(invocation, result, existing, dimensions)


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
def test_engine_rejects_invalid_fragments(
    fragment: object,
    message: str,
    pump_bundle: project.BuildBundle,
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    engine = engine_for_plan(
        pump_bundle.execution_plan, spec_definition=pump_bundle.spec_definition
    )
    dataframe = dataframe_module.DataFrameExecution(
        engine.backend, engine.spec_definition, state_module.RuntimeState()
    )
    operation = next(
        operation
        for operation in engine.plan.invocations
        if operation.entity_id == "pump" and operation.dataset_id == "pump_dataset"
    )

    with pytest.raises(ValueError, match=message):
        dataframe.assemble_fragment(
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


def test_engine_executes_requested_feature_and_its_dependencies(
    example_bundle_factory: example_support.BundleFactory,
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    bundle = example_bundle_factory(features=("health_signal_normalized",))
    engine = engine_for_plan(
        bundle.execution_plan, _engine_parameters(), spec_definition=bundle.spec_definition
    )
    assert [
        feature
        for stage in engine.plan.execution_stages
        for operation in stage
        if operation.function_kind == "vectorize"
        for feature in operation.output_features
    ] == [
        "health_signal_normalized",
    ]
    assert {
        operation.function_kind for stage in engine.plan.execution_stages for operation in stage
    } == {
        "read",
        "collapse",
        "vectorize",
    }

    result = engine.run()

    assert result.datasets["pump_dataset"].collect().height == 2
