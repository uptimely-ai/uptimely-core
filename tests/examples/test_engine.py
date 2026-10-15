import json
import pathlib
import sys

import polars as pl
import pytest
from examples.pump_analytics.functions import calculation

from uptimely import compile
from uptimely import engine as uptimely_engine
from uptimely.cli import cli

ANALYTICS_PATH = pathlib.Path("examples/pump_analytics/_generated/spec/spec.json")
ENGINE_CONFIG_PATH = pathlib.Path("examples/pump_analytics/config/engine.json")


def _engine_bind() -> dict[str, object]:
    engine_config = json.loads(ENGINE_CONFIG_PATH.read_text(encoding="utf-8"))
    return engine_config["bind"]


def test_engine_returns_calculated_features_without_writing_output() -> None:
    engine = uptimely_engine.Engine(ANALYTICS_PATH, bind=_engine_bind())

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
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["uptimely", "engine", "run", "--project-root", "examples/pump_analytics"],
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
    assert "Calculated features: " + ", ".join(expected_features) in capsys.readouterr().out


def test_engine_rejects_unknown_runtime_namespace() -> None:
    engine = uptimely_engine.Engine(ANALYTICS_PATH, bind={})

    result = engine.execute()

    assert any(
        "Unknown runtime namespace: storage" in message for message in result.failures.values()
    )


def test_engine_rejects_unknown_runtime_object() -> None:
    engine = uptimely_engine.Engine(ANALYTICS_PATH, bind={"storage": {}})

    result = engine.execute()

    assert any(
        "Unknown storage object: telemetry_source" in message
        for message in result.failures.values()
    )


def test_engine_rejects_unknown_runtime_attribute() -> None:
    engine = uptimely_engine.Engine(ANALYTICS_PATH, bind={"storage": {"telemetry_source": {}}})

    result = engine.execute()

    assert any(
        "storage object telemetry_source has no attribute: path" in message
        for message in result.failures.values()
    )


def test_engine_merges_fragments_by_entity_dimensions() -> None:
    engine = uptimely_engine.Engine(ANALYTICS_PATH)
    engine._runtime_datasets = {
        ("pump", "pump_dataset"): pl.LazyFrame(
            {
                "plant": ["PLANT-01", "PLANT-01"],
                "production_line": ["LINE-A", "LINE-B"],
                "pump": ["PUMP-101", "PUMP-201"],
                "existing": [1, 2],
            }
        )
    }
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
        for operation in engine.plan.operations
        if operation.entity_id == "pump" and operation.dataset_id == "pump_dataset"
    )
    dimensions = engine.resource_resolver.entity_dimensions(operation.entity_id)
    existing = engine._runtime_datasets[operation.entity_id, operation.dataset_id]
    merged = engine._merge_fragment(existing, fragment, dimensions).collect()

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
    engine = uptimely_engine.Engine(ANALYTICS_PATH)
    operation = next(
        operation
        for operation in engine.plan.operations
        if operation.entity_id == "pump" and operation.dataset_id == "pump_dataset"
    )

    with pytest.raises(ValueError, match=message):
        engine._validate_dataframe_result(
            operation,
            fragment,
            None,
            engine.resource_resolver.entity_dimensions(operation.entity_id),
        )


def test_engine_rejects_ambiguous_dataset_references() -> None:
    engine = uptimely_engine.Engine(ANALYTICS_PATH)
    engine._runtime_datasets = {
        ("first", "shared"): pl.LazyFrame({"id": [1]}),
        ("second", "shared"): pl.LazyFrame({"id": [2]}),
    }

    with pytest.raises(ValueError, match="Ambiguous dataset reference: shared"):
        engine._dataset_by_id("shared")


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
    plan = compile.Compiler(ANALYTICS_PATH, features=["health_signal_normalized"]).compile()
    engine = uptimely_engine.Engine(plan, bind=_engine_bind())
    assert [
        operation.output
        for stage in engine.plan.execution_stages
        for operation in stage
        if operation.kind == "vectorize"
    ] == [
        "health_signal_normalized",
    ]
    assert {operation.kind for stage in engine.plan.execution_stages for operation in stage} == {
        "read",
        "collapse",
        "vectorize",
    }

    result = engine.execute()

    assert result.datasets[("pump", "pump_dataset")].collect().height == 2
