from pathlib import Path

import polars as pl
import pytest

from uptimely.compile import Compiler
from uptimely.compile.node import CallableNode
from uptimely.engine import Engine

SPEC_PATH = Path("examples/example_1/generated/spec/spec.json")


def test_engine_returns_calculated_features_without_writing_output() -> None:
    from examples.example_1.spec.spec import storage_resources

    engine = Engine(SPEC_PATH, runtime_resources={"storage": storage_resources})

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
        engine.calculations[("pump", "pump_dataset", "health_signal_normalized")].element,
        pl.Expr,
    )
    pump_frame = engine.datasets[("pump", "pump_dataset")].collect()
    assert pump_frame.select("pump", "bearing_temperature_max", "health_signal_normalized").sort(
        "pump"
    ).rows() == [
        ("PUMP-101", 68.7, 1.0),
        ("PUMP-201", 64.5, -1.0),
    ]
    telemetry_frame = result.datasets[("pump_telemetry", "pump_telemetry_dataset")].collect()
    assert "pressure_flow_efficiency" in telemetry_frame.columns
    assert "health_signal_normalized" not in telemetry_frame.columns


def test_engine_runner_returns_calculated_feature_ids() -> None:
    from examples.example_1.run_engine import main

    assert main(verbose=False) == [
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


def test_engine_rejects_unknown_runtime_namespace() -> None:
    engine = Engine(SPEC_PATH, runtime_resources={})

    result = engine.execute()

    assert any(
        "Unknown runtime namespace: storage" in message for message in result.failures.values()
    )


def test_engine_rejects_unknown_runtime_object() -> None:
    engine = Engine(SPEC_PATH, runtime_resources={"storage": {}})

    result = engine.execute()

    assert any(
        "Unknown storage object: telemetry_source" in message
        for message in result.failures.values()
    )


def test_engine_rejects_unknown_runtime_attribute() -> None:
    engine = Engine(SPEC_PATH, runtime_resources={"storage": {"telemetry_source": {}}})

    result = engine.execute()

    assert any(
        "storage object telemetry_source has no attribute: path" in message
        for message in result.failures.values()
    )


def test_engine_merges_fragments_by_entity_dimensions() -> None:
    engine = Engine(SPEC_PATH)
    engine.datasets = {
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

    merged = engine._merge_fragment(
        CallableNode(
            function_id="fragment",
            entity="pump",
            operation_type="collapse",
            dataset_id="pump_dataset",
        ),
        fragment,
    ).collect()

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
    engine = Engine(SPEC_PATH)
    engine.datasets = {}
    node = CallableNode(
        function_id="fragment",
        entity="pump",
        operation_type="collapse",
        dataset_id="pump_dataset",
    )

    with pytest.raises(ValueError, match=message):
        engine._merge_fragment(node, fragment)


def test_engine_rejects_ambiguous_dataset_references() -> None:
    engine = Engine(SPEC_PATH)
    engine.datasets = {
        ("first", "shared"): pl.LazyFrame({"id": [1]}),
        ("second", "shared"): pl.LazyFrame({"id": [2]}),
    }

    with pytest.raises(ValueError, match="Ambiguous dataset reference: shared"):
        engine._dataset_by_id("shared")


def test_example_deltas_are_partitioned_and_ordered() -> None:
    from examples.example_1.functions.calculation import (
        bearing_temperature_delta,
        vibration_delta_from_previous,
    )

    frame = pl.DataFrame(
        {
            "pump": ["PUMP-101", "PUMP-201", "PUMP-101", "PUMP-201"],
            "timestamp": [2, 2, 1, 1],
            "bearing_temperature": [11.5, 22.5, 10.0, 20.0],
            "vibration_rms": [1.2, 2.4, 1.0, 2.0],
        }
    )

    result = frame.with_columns(
        bearing_temperature_delta(
            "bearing_temperature",
            ["pump"],
            "timestamp",
        ).alias("temperature_delta"),
        vibration_delta_from_previous(
            "vibration_rms",
            ["pump"],
            "timestamp",
        ).alias("vibration_delta"),
    ).sort("pump", "timestamp")

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


def test_engine_executes_requested_feature_and_its_dependencies(tmp_path: Path) -> None:
    from examples.example_1.spec.spec import storage_resources

    plan = Compiler(SPEC_PATH, features=["health_signal_normalized"]).compile()
    engine = Engine(plan.specification, plan, runtime_resources={"storage": storage_resources})
    assert [
        node.feature for node in engine.callable_order if node.operation_type == "vectorize"
    ] == [
        "health_signal_normalized",
    ]
    assert {node.operation_type for node in engine.callable_order} == {
        "read",
        "collapse",
        "vectorize",
    }

    engine.execute()

    assert engine.datasets[("pump", "pump_dataset")].collect().height == 2
