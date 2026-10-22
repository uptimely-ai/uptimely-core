import json
import pathlib
import shutil
import sys

import polars as pl
import pytest
from conftest import EXAMPLES_ROOT, engine_for_plan
from examples.pump_analytics.functions import calculation

from uptimely import compiler
from uptimely import project as project_module
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
    return compiler.Compiler(spec_module.load_spec(SPEC_PATH)).compile()


def _copy_pump_project(tmp_path: pathlib.Path) -> pathlib.Path:
    project_root = tmp_path / "examples" / "pump_analytics"
    shutil.copytree(
        EXAMPLES_ROOT / "pump_analytics",
        project_root,
        ignore=shutil.ignore_patterns("_generated"),
    )
    (project_root.parent / "__init__.py").write_text("", encoding="utf-8")
    return project_root


def test_engine_returns_calculated_features_without_writing_output() -> None:
    engine = engine_for_plan(_execution_plan(), _engine_bind())

    result = engine.execute()

    assert not result.failures
    assert sorted({feature for _, _, feature in result.calculated_outputs}) == [
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
        result.calculated_outputs[("pump", "pump_dataset", "health_signal_normalized")],
        pl.LazyFrame,
    )
    pump_frame = result.datasets[("pump", "pump_dataset")].collect()
    assert pump_frame.select("pump", "bearing_temperature_max", "health_signal_normalized").sort(
        "pump"
    ).rows() == [
        ("PUMP-101", 68.7, 1.0),
        ("PUMP-201", 64.5, -1.0),
    ]
    telemetry_frame = result.datasets[("pump_telemetry", "pump_telemetry_dataset")].collect()
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


def test_engine_cli_reports_calculated_feature_ids(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project_root = _copy_pump_project(tmp_path)
    project_module.build_project(project_root)
    monkeypatch.setattr(
        sys,
        "argv",
        ["uptimely", "engine", "run", "--project-root", str(project_root)],
    )
    cli.main()

    expected_features = [
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
    output = capsys.readouterr().out
    assert "Build scope: all features" in output
    assert "Calculated features: " + ", ".join(expected_features) in output


def test_engine_cli_reports_scoped_saved_build(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project_root = _copy_pump_project(tmp_path)
    project_module.build_project(project_root, features=["health_signal_normalized"])
    monkeypatch.setattr(
        sys,
        "argv",
        ["uptimely", "engine", "run", "--project-root", str(project_root)],
    )

    cli.main()

    output = capsys.readouterr().out
    assert "Build scope: selected features: health_signal_normalized" in output
    assert "Calculated features: health_signal_normalized" in output


def test_simple_analytics_engine_cli_executes_saved_build(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project_root = EXAMPLES_ROOT / "simple_analytics"
    monkeypatch.setattr(
        sys,
        "argv",
        ["uptimely", "engine", "run", "--project-root", str(project_root)],
    )

    cli.main()

    output = capsys.readouterr().out
    assert "Build scope: all features" in output
    assert "Calculated features: column_3, column_4" in output
    result_lines = [line for line in output.splitlines() if line.startswith("[")]
    assert len(result_lines) == 1
    assert json.loads(result_lines[0]) == [
        {"column_3": 3, "column_4": True},
        {"column_3": 7, "column_4": True},
    ]


def test_engine_rejects_unknown_runtime_namespace() -> None:
    engine = engine_for_plan(_execution_plan(), {})

    result = engine.execute()

    assert any(
        "Unknown runtime namespace: storage" in message for message in result.failures.values()
    )


def test_engine_rejects_unknown_runtime_object() -> None:
    engine = engine_for_plan(_execution_plan(), {"storage": {}})

    result = engine.execute()

    assert any(
        "Unknown storage object: telemetry_source" in message
        for message in result.failures.values()
    )


def test_engine_rejects_unknown_runtime_attribute() -> None:
    engine = engine_for_plan(_execution_plan(), {"storage": {"telemetry_source": {}}})

    result = engine.execute()

    assert any(
        "storage object telemetry_source has no attribute: path" in message
        for message in result.failures.values()
    )


def test_engine_merges_fragments_by_entity_dimensions() -> None:
    engine = engine_for_plan(_execution_plan())
    dataframe = dataframe_module.DataFrameExecution(
        engine.backend, engine.resources, state_module.RuntimeState()
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
        for operation in engine.plan.callables
        if operation.entity_id == "pump" and operation.dataset_id == "pump_dataset"
    )
    dimensions = engine.resources["entities"][operation.entity_id]["dimensions"]
    merged = dataframe.merge_fragment(existing, fragment, dimensions).collect()

    assert merged.select("pump", "existing", "new").sort("pump").rows() == [
        ("PUMP-101", 1, 10),
        ("PUMP-201", 2, 20),
    ]


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
    engine = engine_for_plan(_execution_plan())
    dataframe = dataframe_module.DataFrameExecution(
        engine.backend, engine.resources, state_module.RuntimeState()
    )
    operation = next(
        operation
        for operation in engine.plan.callables
        if operation.entity_id == "pump" and operation.dataset_id == "pump_dataset"
    )

    with pytest.raises(ValueError, match=message):
        dataframe.validate_result(
            operation,
            fragment,
            None,
            engine.resources["entities"][operation.entity_id]["dimensions"],
        )


def test_engine_rejects_ambiguous_dataset_references() -> None:
    state = state_module.RuntimeState(
        datasets={
            ("first", "shared"): pl.LazyFrame({"id": [1]}),
            ("second", "shared"): pl.LazyFrame({"id": [2]}),
        }
    )

    with pytest.raises(ValueError, match="Ambiguous dataset reference: shared"):
        state.dataset_by_id("shared")


def test_example_deltas_are_partitioned_and_ordered() -> None:
    frame = pl.DataFrame(
        {
            "pump": ["PUMP-101", "PUMP-201", "PUMP-101", "PUMP-201"],
            "timestamp": [2, 2, 1, 1],
            "bearing_temperature": [11.5, 22.5, 10.0, 20.0],
            "vibration_rms": [1.2, 2.4, 1.0, 2.0],
        }
    )

    result = calculation.bearing_temperature_delta(
        "bearing_temperature",
        ["pump"],
        "timestamp",
        frame.lazy(),
        "temperature_delta",
    )
    result = (
        calculation.vibration_delta_from_previous(
            "vibration_rms",
            ["pump"],
            "timestamp",
            result,
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
    plan = compiler.Compiler(SPEC_PATH, features=["health_signal_normalized"]).compile()
    engine = engine_for_plan(plan, _engine_bind())
    assert [
        operation.output
        for stage in engine.plan.execution_stages
        for operation in stage
        if operation.operation == "vectorize"
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

    result = engine.execute()

    assert result.datasets[("pump", "pump_dataset")].collect().height == 2
