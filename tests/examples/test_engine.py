import pathlib

import polars as pl
import pytest
from examples.example_1 import run_engine
from examples.example_1.functions import calculation
from examples.example_1.spec import spec

from uptimely import compile
from uptimely import engine as uptimely_engine

SPEC_PATH = pathlib.Path("examples/example_1/_generated/spec/spec.json")


def test_engine_returns_calculated_features_without_writing_output() -> None:
    engine = uptimely_engine.Engine(
        SPEC_PATH, runtime_resources={"storage": spec.storage_resources}
    )

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
    assert "pressure_flow_efficiency" in telemetry_frame.columns
    assert "health_signal_normalized" not in telemetry_frame.columns


def test_engine_runner_returns_calculated_feature_ids() -> None:
    assert run_engine.main(verbose=False) == [
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
    engine = uptimely_engine.Engine(SPEC_PATH, runtime_resources={})

    result = engine.execute()

    assert any(
        "Unknown runtime namespace: storage" in message for message in result.failures.values()
    )


def test_engine_rejects_unknown_runtime_object() -> None:
    engine = uptimely_engine.Engine(SPEC_PATH, runtime_resources={"storage": {}})

    result = engine.execute()

    assert any(
        "Unknown storage object: telemetry_source" in message
        for message in result.failures.values()
    )


def test_engine_rejects_unknown_runtime_attribute() -> None:
    engine = uptimely_engine.Engine(
        SPEC_PATH, runtime_resources={"storage": {"telemetry_source": {}}}
    )

    result = engine.execute()

    assert any(
        "storage object telemetry_source has no attribute: path" in message
        for message in result.failures.values()
    )


def test_engine_merges_fragments_by_entity_dimensions() -> None:
    engine = uptimely_engine.Engine(SPEC_PATH)
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
    engine = uptimely_engine.Engine(SPEC_PATH)
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
    engine = uptimely_engine.Engine(SPEC_PATH)
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
    plan = compile.Compiler(SPEC_PATH, features=["health_signal_normalized"]).compile()
    engine = uptimely_engine.Engine(plan, runtime_resources={"storage": spec.storage_resources})
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
