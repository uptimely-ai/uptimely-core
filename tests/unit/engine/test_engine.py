from dataclasses import replace
from pathlib import Path

import polars as pl
import pytest

from uptimely.engine import Engine, EngineConfig
from uptimely.plan import ExecutionPlan, Plan

PLAN_PATH = Path(__file__).parents[2] / "fixtures" / "plans" / "simple_engine.json"


def _plan() -> ExecutionPlan:
    return ExecutionPlan.from_json(PLAN_PATH)


def test_execute_runs_stages_and_returns_runtime_outputs() -> None:
    written: dict[str, object] = {}

    def read(source: str) -> pl.DataFrame:
        assert source == "/tmp/telemetry.parquet"
        return pl.DataFrame({"asset_id": ["A", "B"], "reading": [2, 3]})

    def double(column: str) -> pl.Expr:
        return pl.col(column) * 2

    def write(dataset: pl.DataFrame, features: list[str]) -> None:
        written["dataset"] = dataset
        written["features"] = features

    engine = Engine(
        _plan(),
        runtime_resources={"storage": {"source": {"path": "/tmp/telemetry.parquet"}}},
        callable_loader=_Loader({"test:read": read, "test:double": double, "test:write": write}),
    )

    result = engine.execute()

    assert set(result.operation_statuses.values()) == {"succeeded"}
    assert result.failures == {}
    assert result.plan_version == "1.0.0"
    assert isinstance(result.calculated_outputs["asset", "telemetry", "doubled"], pl.Expr)
    assert engine.datasets["asset", "telemetry"].select("doubled").to_series().to_list() == [4, 6]
    assert written["features"] == ["doubled"]
    assert written["dataset"].select("asset_id", "doubled").rows() == [("A", 4), ("B", 6)]


def test_execute_stops_after_a_failed_operation() -> None:
    called = False

    def read(source: str) -> pl.DataFrame:
        raise RuntimeError("source unavailable")

    def write(dataset: object, features: list[str]) -> None:
        nonlocal called
        called = True

    engine = Engine(
        _plan(),
        runtime_resources={"storage": {"source": {"path": "/tmp/telemetry.parquet"}}},
        callable_loader=_Loader({"test:read": read, "test:write": write}),
    )

    result = engine.execute()

    read_id = "callable:read:load:asset:telemetry:reading"
    write_id = "callable:write:save:asset:telemetry:doubled"
    assert result.operation_statuses[read_id] == "failed"
    assert "source unavailable" in result.failures[read_id]
    assert result.operation_statuses[write_id] == "skipped"
    assert called is False


def test_engine_validates_plan_backend_and_specification_version() -> None:
    plan = _plan().plan

    with pytest.raises(ValueError, match="Unsupported plan backend"):
        Engine(ExecutionPlan(Plan(**{**plan.__dict__, "required_backend": "pandas"})))

    with pytest.raises(ValueError, match="Specification version mismatch"):
        Engine(
            _plan(),
            resources={"specification_version": "2025.01"},
        )


@pytest.mark.parametrize("reference", ["?", "?storage.source", "?storage.source.path.extra"])
def test_engine_rejects_malformed_runtime_references(reference: str) -> None:
    engine = Engine(_plan())

    with pytest.raises(ValueError, match="Malformed runtime reference"):
        engine._resolve_runtime_reference(reference)


def test_engine_rejects_ambiguous_fragment_references() -> None:
    engine = Engine(_plan())
    engine._runtime_fragments = {
        ("first", "shared"): pl.DataFrame({"asset_id": ["A"]}),
        ("second", "shared"): pl.DataFrame({"asset_id": ["B"]}),
    }

    with pytest.raises(ValueError, match="Ambiguous fragment reference: shared"):
        engine._dataframe_by_id("shared")


def test_execute_reports_unsupported_operation_types() -> None:
    plan = _plan().plan
    invalid_operation = replace(plan.operations[0], kind="unsupported")
    engine = Engine(
        ExecutionPlan(
            Plan(**{**plan.__dict__, "operations": [invalid_operation, *plan.operations[1:]]})
        )
    )

    result = engine.execute()

    assert result.operation_statuses[invalid_operation.id] == "failed"
    assert result.failures[invalid_operation.id] == "Unsupported operation type: unsupported"


def test_execute_converts_scalar_calculations_to_columns() -> None:
    def read(source: str) -> pl.DataFrame:
        return pl.DataFrame({"asset_id": ["A"], "reading": [2]})

    def constant(column: str) -> int:
        return 10

    engine = Engine(
        _plan(),
        runtime_resources={"storage": {"source": {"path": "/tmp/telemetry.parquet"}}},
        callable_loader=_Loader(
            {"test:read": read, "test:double": constant, "test:write": lambda **_: None}
        ),
    )

    result = engine.execute()

    assert result.failures == {}
    assert engine.datasets["asset", "telemetry"].select("doubled").item() == 10


@pytest.mark.parametrize("batch_size", [0, -1, True, "100"])
def test_engine_config_rejects_invalid_batch_size(batch_size: object) -> None:
    with pytest.raises(ValueError, match="batch_size"):
        EngineConfig(batch_size=batch_size)


@pytest.mark.parametrize("dataframe", ["pandas", "", None])
def test_engine_config_rejects_unsupported_dataframe_backend(dataframe: object) -> None:
    with pytest.raises(ValueError, match="Unsupported dataframe backend"):
        EngineConfig(dataframe=dataframe)  # type: ignore[arg-type]


class _Loader:
    def __init__(self, callables: dict[str, object]) -> None:
        self.callables = callables

    def load(self, entrypoint: str):
        return self.callables[entrypoint]
