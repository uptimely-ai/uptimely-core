import dataclasses
import pathlib

import polars as pl
import pytest
from conftest import bundle_for_plan

from uptimely import compiler as uptimely_compiler
from uptimely import engine as uptimely_engine
from uptimely import entrypoint as entrypoint_module
from uptimely import spec
from uptimely.compiler import plan as uptimely_plan
from uptimely.engine import bindings as bindings_module
from uptimely.engine import state as state_module
from uptimely.spec.python import bind, dataset, dimension, feature, mapping, ref

PLAN_PATH = pathlib.Path(__file__).parents[2] / "fixtures" / "plans" / "simple_engine.json"


def _plan() -> uptimely_plan.ExecutionPlan:
    return uptimely_plan.ExecutionPlan.from_json(PLAN_PATH)


def _engine(
    plan: uptimely_plan.ExecutionPlan,
    bind_values: dict[str, dict[str, dict[str, object]]] | None = None,
    project_root: pathlib.Path | None = None,
) -> uptimely_engine.Engine:
    return uptimely_engine.Engine(
        bundle_for_plan(plan, project_root), uptimely_engine.EngineConfig(bind=bind_values or {})
    )


def _patch_callables(monkeypatch: pytest.MonkeyPatch, callables: dict[str, object]) -> None:
    class _TestEntrypoint:
        def __init__(self, location: str, _root: pathlib.Path) -> None:
            self.location = location

        @property
        def function(self) -> object:
            return self

        def load(self) -> object:
            return callables[self.location]

    monkeypatch.setattr(entrypoint_module, "Entrypoint", _TestEntrypoint)


def test_execute_runs_stages_and_returns_runtime_outputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    written: dict[str, object] = {}

    def read(source: str) -> pl.DataFrame:
        assert source == "/tmp/telemetry.parquet"
        return pl.DataFrame({"asset_id": ["A", "B"], "reading": [2, 3]})

    def double(column: str, dataset: pl.DataFrame) -> pl.DataFrame:
        return dataset.with_columns((pl.col(column) * 2).alias("doubled"))

    def write(dataset: pl.DataFrame, features: list[str]) -> None:
        written["dataset"] = dataset
        written["features"] = features

    _patch_callables(monkeypatch, {"test:read": read, "test:double": double, "test:write": write})
    engine = _engine(_plan(), {"storage": {"source": {"path": "/tmp/telemetry.parquet"}}})

    result = engine.execute()

    assert set(result.callable_statuses.values()) == {"succeeded"}
    assert result.failures == {}
    assert result.plan_version == 1
    assert isinstance(result.calculated_outputs["asset", "telemetry", "doubled"], pl.DataFrame)
    assert result.datasets["asset", "telemetry"].select("doubled").to_series().to_list() == [
        4,
        6,
    ]
    assert written["features"] == ["doubled"]
    assert written["dataset"].select("asset_id", "doubled").rows() == [("A", 4), ("B", 6)]


def test_saved_plan_executes_without_compiler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved_plan = _plan()

    def read(source: str) -> pl.DataFrame:
        assert source == "/tmp/telemetry.parquet"
        return pl.DataFrame({"asset_id": ["A", "B"], "reading": [2, 3]})

    def double(column: str, dataset: pl.DataFrame) -> pl.DataFrame:
        return dataset.with_columns((pl.col(column) * 2).alias("doubled"))

    def write(dataset: pl.DataFrame, features: list[str]) -> None:
        assert features == ["doubled"]

    def fail_compile(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Saved-plan execution must not compile spec")

    monkeypatch.setattr(uptimely_compiler.Compiler, "compile", fail_compile)
    _patch_callables(monkeypatch, {"test:read": read, "test:double": double, "test:write": write})
    engine = _engine(saved_plan, {"storage": {"source": {"path": "/tmp/telemetry.parquet"}}})

    result = engine.execute()

    assert result.failures == {}
    assert result.datasets["asset", "telemetry"]["doubled"].to_list() == [4, 6]


def test_repeated_execution_does_not_leak_runtime_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    read_count = 0

    def read(source: str) -> pl.DataFrame:
        nonlocal read_count
        assert source == "/tmp/telemetry.parquet"
        read_count += 1
        return pl.DataFrame({"asset_id": ["A", "B"], "reading": [read_count, read_count + 1]})

    def double(column: str, dataset: pl.DataFrame) -> pl.DataFrame:
        return dataset.with_columns((pl.col(column) * 2).alias("doubled"))

    def write(dataset: pl.DataFrame, features: list[str]) -> None:
        assert features == ["doubled"]
        assert dataset["doubled"].to_list() in ([2, 4], [4, 6])

    _patch_callables(monkeypatch, {"test:read": read, "test:double": double, "test:write": write})
    engine = _engine(_plan(), {"storage": {"source": {"path": "/tmp/telemetry.parquet"}}})

    first_result = engine.execute()
    second_result = engine.execute()

    assert first_result.failures == second_result.failures == {}
    assert first_result.datasets is not second_result.datasets
    assert first_result.calculated_outputs is not second_result.calculated_outputs
    assert first_result.datasets["asset", "telemetry"]["doubled"].to_list() == [2, 4]
    assert second_result.datasets["asset", "telemetry"]["doubled"].to_list() == [4, 6]
    first_output = first_result.calculated_outputs["asset", "telemetry", "doubled"]
    assert first_output["doubled"].to_list() == [2, 4]


def test_execute_stops_after_a_failed_operation(monkeypatch: pytest.MonkeyPatch) -> None:
    called = False

    def read(source: str) -> pl.DataFrame:
        raise RuntimeError("source unavailable")

    def write(dataset: object, features: list[str]) -> None:
        nonlocal called
        called = True

    _patch_callables(monkeypatch, {"test:read": read, "test:write": write})
    engine = _engine(_plan(), {"storage": {"source": {"path": "/tmp/telemetry.parquet"}}})

    result = engine.execute()

    read_id = "callable:read:load:asset:telemetry:reading"
    write_id = "callable:write:save:asset:telemetry:doubled"
    assert result.callable_statuses[read_id] == "failed"
    assert "source unavailable" in result.failures[read_id]
    assert result.callable_statuses[write_id] == "skipped"
    assert result.callable_statuses == {
        callable.id: "failed" if callable.id == read_id else "skipped"
        for callable in engine.plan.callables
    }
    assert set(result.durations) == {read_id}
    assert called is False


@pytest.mark.parametrize(
    "return_value",
    [
        None,
        42,
        object(),
        {"non_serializable": object()},
        pl.DataFrame({"unrelated": [1]}),
    ],
)
def test_escape_ignores_any_return_without_materializing_features(
    return_value: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    callable_id = "callable:escape:external_action:asset:external:action"
    escape = uptimely_plan.Callable(
        id=callable_id,
        operation="escape",
        entrypoint="test:escape",
        entity_id="asset",
        dataset_id="external",
        output="external_result",
        output_features=["external_result"],
        input_features=["external_input"],
    )
    plan = uptimely_plan.ExecutionPlan(
        uptimely_plan.Plan(
            plan_version=1,
            required_backend="polars",
            resources={
                "entities": {"asset": {"dimensions": []}},
                "functions": {
                    "external_action": {
                        "operation": "escape",
                        "returns": "any",
                        "args": {},
                    }
                },
            },
            callables=[escape],
            stages=[[callable_id]],
        )
    )
    _patch_callables(monkeypatch, {"test:escape": lambda: return_value})
    engine = _engine(plan)

    result = engine.execute()

    assert result.callable_statuses == {callable_id: "succeeded"}
    assert result.failures == {}
    assert result.datasets == {}
    assert result.calculated_outputs == {}


def test_escape_chain_runs_without_materializing_declared_feature_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_id = "callable:escape:first:asset:external:first"
    second_id = "callable:escape:second:asset:external:second"
    calls: list[str] = []

    def first() -> int:
        calls.append("first")
        return 17

    def second() -> object:
        calls.append("second")
        return object()

    first_callable = uptimely_plan.Callable(
        id=first_id,
        operation="escape",
        entrypoint="test:first",
        entity_id="asset",
        dataset_id="external",
        output="first_output",
        output_features=["first_output"],
        input_features=["external_input"],
    )
    second_callable = uptimely_plan.Callable(
        id=second_id,
        operation="escape",
        entrypoint="test:second",
        entity_id="asset",
        dataset_id="external",
        output="second_output",
        output_features=["second_output"],
        input_features=["first_output"],
        dependency_ids=[first_id],
    )
    plan = uptimely_plan.ExecutionPlan(
        uptimely_plan.Plan(
            plan_version=1,
            required_backend="polars",
            resources={
                "entities": {"asset": {"dimensions": []}},
                "functions": {
                    function_id: {"operation": "escape", "returns": "any", "args": {}}
                    for function_id in ("first", "second")
                },
            },
            callables=[first_callable, second_callable],
            stages=[[first_id], [second_id]],
        )
    )

    _patch_callables(monkeypatch, {"test:first": first, "test:second": second})
    result = _engine(plan).execute()

    assert calls == ["first", "second"]
    assert result.callable_statuses == {first_id: "succeeded", second_id: "succeeded"}
    assert result.failures == {}
    assert result.datasets == {}
    assert result.calculated_outputs == {}


def test_escape_resolves_literal_and_runtime_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    callable_id = "callable:escape:external_action:asset:external:action"
    escape = uptimely_plan.Callable(
        id=callable_id,
        operation="escape",
        entrypoint="test:escape",
        entity_id="asset",
        dataset_id="external",
        output="external_result",
        output_features=["external_result"],
        input_features=["external_input"],
        arguments={"path": "?storage.output.path", "mode": "replace"},
    )
    plan = uptimely_plan.ExecutionPlan(
        uptimely_plan.Plan(
            plan_version=1,
            required_backend="polars",
            resources={
                "entities": {"asset": {"dimensions": []}},
                "functions": {
                    "external_action": {
                        "operation": "escape",
                        "returns": "any",
                        "args": {
                            "path": {"type": "string"},
                            "mode": {"type": "string"},
                        },
                    }
                },
            },
            callables=[escape],
            stages=[[callable_id]],
        )
    )
    received: list[tuple[str, str]] = []

    def external_action(path: str, mode: str) -> None:
        received.append((path, mode))

    _patch_callables(monkeypatch, {"test:escape": external_action})
    result = _engine(plan, {"storage": {"output": {"path": "/tmp/external-output.csv"}}}).execute()

    assert received == [("/tmp/external-output.csv", "replace")]
    assert result.callable_statuses == {callable_id: "succeeded"}
    assert result.failures == {}


def test_escape_unavailable_dataframe_binding_fails_and_skips_downstream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_id = "callable:escape:first:asset:external:first"
    second_id = "callable:escape:second:asset:external:second"
    first_callable = uptimely_plan.Callable(
        id=first_id,
        operation="escape",
        entrypoint="test:first",
        entity_id="asset",
        dataset_id="external",
        output="external_result",
        output_features=["external_result"],
        input_features=["external_input"],
        arguments={"frame": "missing"},
    )
    second_callable = dataclasses.replace(
        first_callable,
        id=second_id,
        entrypoint="test:second",
        output="downstream_result",
        output_features=["downstream_result"],
        dependency_ids=[first_id],
    )
    plan = uptimely_plan.ExecutionPlan(
        uptimely_plan.Plan(
            plan_version=1,
            required_backend="polars",
            resources={
                "entities": {"asset": {"dimensions": []}},
                "functions": {
                    function_id: {
                        "operation": "escape",
                        "returns": "any",
                        "args": {"frame": {"type": "dataframe"}},
                    }
                    for function_id in ("first", "second")
                },
            },
            callables=[first_callable, second_callable],
            stages=[[first_id], [second_id]],
        )
    )

    _patch_callables(monkeypatch, {"test:first": lambda **_: None, "test:second": lambda **_: None})
    result = _engine(plan).execute()

    assert result.callable_statuses == {first_id: "failed", second_id: "skipped"}
    assert "Dataset dataframe is unavailable: missing" in result.failures[first_id]


def test_escape_resolves_dataframe_arguments_from_preceding_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    read_id = "callable:read:load:asset:telemetry:load"
    escape_id = "callable:escape:external_action:asset:telemetry:action"
    observed: list[pl.DataFrame] = []

    def read() -> pl.DataFrame:
        return pl.DataFrame({"asset_id": ["A"], "reading": [3]})

    def external_action(dataset: pl.DataFrame) -> object:
        observed.append(dataset)
        return object()

    read_callable = uptimely_plan.Callable(
        id=read_id,
        operation="read",
        entrypoint="test:read",
        entity_id="asset",
        dataset_id="telemetry",
        output="load",
        output_features=["asset_id", "reading"],
    )
    escape_callable = uptimely_plan.Callable(
        id=escape_id,
        operation="escape",
        entrypoint="test:escape",
        entity_id="asset",
        dataset_id="telemetry",
        output="external_result",
        output_features=["external_result"],
        input_features=["reading"],
        arguments={"dataset": "telemetry"},
        dependency_ids=[read_id],
    )
    plan = uptimely_plan.ExecutionPlan(
        uptimely_plan.Plan(
            plan_version=1,
            required_backend="polars",
            resources={
                "entities": {"asset": {"dimensions": ["asset_id"]}},
                "functions": {
                    "load": {"operation": "read", "returns": "dataframe", "args": {}},
                    "external_action": {
                        "operation": "escape",
                        "returns": "any",
                        "args": {"dataset": {"type": "dataframe"}},
                    },
                },
            },
            callables=[read_callable, escape_callable],
            stages=[[read_id], [escape_id]],
        )
    )

    _patch_callables(monkeypatch, {"test:read": read, "test:escape": external_action})
    result = _engine(plan).execute()

    assert result.failures == {}
    assert result.callable_statuses == {read_id: "succeeded", escape_id: "succeeded"}
    assert observed == [result.datasets["asset", "telemetry"]]
    assert "external_result" not in result.datasets["asset", "telemetry"].columns
    assert result.calculated_outputs == {}


def test_escape_exception_fails_and_skips_downstream(monkeypatch: pytest.MonkeyPatch) -> None:
    first_id = "callable:escape:first:asset:external:first"
    second_id = "callable:escape:second:asset:external:second"
    first_callable = uptimely_plan.Callable(
        id=first_id,
        operation="escape",
        entrypoint="test:first",
        entity_id="asset",
        dataset_id="external",
        output="external_result",
        output_features=["external_result"],
        input_features=["external_input"],
    )
    second_callable = dataclasses.replace(
        first_callable,
        id=second_id,
        entrypoint="test:second",
        output="downstream_result",
        output_features=["downstream_result"],
        dependency_ids=[first_id],
    )
    plan = uptimely_plan.ExecutionPlan(
        uptimely_plan.Plan(
            plan_version=1,
            required_backend="polars",
            resources={
                "entities": {"asset": {"dimensions": []}},
                "functions": {
                    function_id: {"operation": "escape", "returns": "any", "args": {}}
                    for function_id in ("first", "second")
                },
            },
            callables=[first_callable, second_callable],
            stages=[[first_id], [second_id]],
        )
    )

    def fail() -> None:
        raise RuntimeError("external action failed")

    _patch_callables(monkeypatch, {"test:first": fail, "test:second": lambda: None})
    result = _engine(plan).execute()

    assert result.callable_statuses == {first_id: "failed", second_id: "skipped"}
    assert result.failures == {first_id: "external action failed"}


def test_python_spec_escape_executes_after_json_plan_reload_with_local_storage(
    tmp_path: pathlib.Path,
) -> None:
    source_path = tmp_path / "input.csv"
    output_path = tmp_path / "output.csv"
    plan_path = tmp_path / "execution_plan.json"
    source_path.write_text("asset_id,value\nA,2\nB,3\n", encoding="utf-8")
    module_path = tmp_path / "external_action.py"
    module_path.write_text(
        "import polars as pl\n"
        f"SOURCE = {str(source_path)!r}\n"
        f"OUTPUT = {str(output_path)!r}\n"
        "def process() -> None:\n"
        "    frame = pl.read_csv(SOURCE)\n"
        "    result = frame.with_columns((pl.col('value') * 2).alias('external_result'))\n"
        "    result.write_csv(OUTPUT)\n",
        encoding="utf-8",
    )
    declaration = dataset.Dataset(
        id="external",
        mappings=[
            mapping.Mapping(
                id="external_action",
                bind=bind.bind(ref.function(f"{module_path}:process", operation="escape")),
                inputs=[ref.feature("asset_id")],
                outputs=[feature.Feature(id="external_result")],
            )
        ],
    )
    spec_definition = spec.from_python(
        datasets=[declaration],
        dimensions=[dimension.Dimension(id="asset_id", type="string")],
    )

    compiled = uptimely_compiler.Compiler(spec_definition, features=["external_result"]).compile()
    compiled.export_json(plan_path)
    restored = uptimely_plan.ExecutionPlan.from_json(plan_path)
    result = _engine(restored, project_root=tmp_path).execute()

    assert result.failures == {}
    assert result.callable_statuses == {compiled.callables[0].id: "succeeded"}
    assert result.datasets == {}
    assert result.calculated_outputs == {}
    assert pl.read_csv(output_path).rows() == [("A", 2, 4), ("B", 3, 6)]


def test_engine_validates_plan_backend() -> None:
    plan = _plan().plan

    with pytest.raises(ValueError, match="Unsupported plan backend"):
        _engine(
            uptimely_plan.ExecutionPlan(
                uptimely_plan.Plan(**{**plan.__dict__, "required_backend": "pandas"})
            )
        )


def test_engine_selects_dataframe_backend_from_config() -> None:
    engine = uptimely_engine.Engine(
        bundle_for_plan(_plan()),
        uptimely_engine.EngineConfig(backend={"dataframe": "POLARS"}),
    )

    assert isinstance(engine.backend, uptimely_engine.PolarsBackend)


def test_engine_rejects_spec_paths_instead_of_compiling() -> None:
    with pytest.raises(ValueError, match="bundle must be a BuildBundle"):
        uptimely_engine.Engine("spec.json", uptimely_engine.EngineConfig())  # type: ignore[arg-type]

    assert not hasattr(uptimely_engine.Engine, "from_spec")
    assert not hasattr(uptimely_engine.Engine, "spec")


def test_engine_rejects_execution_plan_instead_of_bundle() -> None:
    with pytest.raises(ValueError, match="bundle must be a BuildBundle"):
        uptimely_engine.Engine(
            _plan(),
            uptimely_engine.EngineConfig(),  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("reference", ["?", "?storage.source", "?storage.source.path.extra"])
def test_engine_rejects_malformed_runtime_references(reference: str) -> None:
    engine = _engine(_plan())
    bindings = bindings_module.RuntimeBindings(
        engine.resources, state_module.RuntimeState(), engine.bind
    )

    with pytest.raises(ValueError, match="Malformed runtime reference"):
        bindings.resolve_runtime_reference(reference)


def test_engine_rejects_ambiguous_fragment_references() -> None:
    state = state_module.RuntimeState(
        fragments={
            ("first", "shared"): pl.DataFrame({"asset_id": ["A"]}),
            ("second", "shared"): pl.DataFrame({"asset_id": ["B"]}),
        }
    )

    with pytest.raises(ValueError, match="Ambiguous fragment reference: shared"):
        state.dataframe_by_id("shared")


def test_runtime_state_prefers_dataset_to_fragment_lookup() -> None:
    dataset = pl.DataFrame({"asset_id": ["dataset"]})
    fragment = pl.DataFrame({"asset_id": ["fragment"]})
    state = state_module.RuntimeState(
        datasets={("first", "shared"): dataset},
        fragments={("first", "shared"): fragment},
    )

    assert state.dataframe_by_id("shared") is dataset


def test_runtime_state_is_not_shared_between_instances() -> None:
    first = state_module.RuntimeState()
    second = state_module.RuntimeState()
    first.datasets["asset", "telemetry"] = pl.DataFrame({"asset_id": ["A"]})

    assert second.datasets == {}


def test_execute_reports_unsupported_operation_types() -> None:
    plan = _plan().plan
    invalid_callable = dataclasses.replace(plan.callables[0], operation="unsupported")
    engine = _engine(
        uptimely_plan.ExecutionPlan(
            uptimely_plan.Plan(
                **{**plan.__dict__, "callables": [invalid_callable, *plan.callables[1:]]}
            )
        )
    )

    result = engine.execute()

    assert result.callable_statuses[invalid_callable.id] == "failed"
    assert result.failures[invalid_callable.id] == "Unsupported callable operation: unsupported"


def test_execute_rejects_scalar_calculations(monkeypatch: pytest.MonkeyPatch) -> None:
    def read(source: str) -> pl.DataFrame:
        return pl.DataFrame({"asset_id": ["A"], "reading": [2]})

    def constant(column: str, dataset: pl.DataFrame) -> int:
        return 10

    _patch_callables(
        monkeypatch,
        {"test:read": read, "test:double": constant, "test:write": lambda **_: None},
    )
    engine = _engine(_plan(), {"storage": {"source": {"path": "/tmp/telemetry.parquet"}}})

    result = engine.execute()

    assert "must return a Polars DataFrame or LazyFrame" in next(iter(result.failures.values()))


def test_vectorize_mapping_emits_multiple_features_with_one_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def read() -> pl.DataFrame:
        return pl.DataFrame({"asset_id": ["A"], "reading": [3]})

    def calculate() -> pl.DataFrame:
        nonlocal calls
        calls += 1
        return pl.DataFrame(
            {
                "asset_id": ["A"],
                "reading_plus_one": [4],
                "reading_times_two": [6],
            }
        )

    read_callable = uptimely_plan.Callable(
        id="callable:read:load:asset:telemetry:load",
        operation="read",
        entrypoint="test:read",
        entity_id="asset",
        dataset_id="telemetry",
        output="load",
        output_features=["asset_id", "reading"],
    )
    vectorize_callable = uptimely_plan.Callable(
        id="callable:vectorize:calculate:asset:telemetry:reading_plus_one",
        operation="vectorize",
        entrypoint="test:calculate",
        entity_id="asset",
        dataset_id="telemetry",
        output="reading_plus_one",
        output_features=["reading_plus_one", "reading_times_two"],
        dependency_ids=[read_callable.id],
    )
    plan = uptimely_plan.ExecutionPlan(
        uptimely_plan.Plan(
            plan_version=1,
            required_backend="polars",
            resources={
                "entities": {"asset": {"dimensions": ["asset_id"]}},
                "functions": {
                    "load": {"operation": "read", "args": {}},
                    "calculate": {"operation": "vectorize", "args": {}},
                },
            },
            callables=[read_callable, vectorize_callable],
            stages=[[read_callable.id], [vectorize_callable.id]],
        )
    )
    _patch_callables(monkeypatch, {"test:read": read, "test:calculate": calculate})
    engine = _engine(plan)

    result = engine.execute()

    assert result.failures == {}
    assert calls == 1
    assert result.datasets["asset", "telemetry"].select(
        "reading_plus_one", "reading_times_two"
    ).rows() == [(4, 6)]
    assert set(result.calculated_outputs) == {
        ("asset", "telemetry", "reading_plus_one"),
        ("asset", "telemetry", "reading_times_two"),
    }


@pytest.mark.parametrize("batch_size", [0, -1, True, "100"])
def test_engine_config_rejects_invalid_batch_size(batch_size: object) -> None:
    with pytest.raises(ValueError, match="batch_size"):
        uptimely_engine.EngineBackendConfig(batch_size=batch_size)


@pytest.mark.parametrize("dataframe", ["pandas", ""])
def test_engine_config_rejects_unsupported_dataframe_backend(dataframe: object) -> None:
    configuration = uptimely_engine.EngineConfig(backend={"dataframe": dataframe})
    with pytest.raises(ValueError, match="Unsupported dataframe backend"):
        uptimely_engine.Engine(bundle_for_plan(_plan()), configuration)


def test_engine_config_rejects_non_string_dataframe_backend() -> None:
    with pytest.raises(ValueError, match="dataframe"):
        uptimely_engine.EngineConfig(backend={"dataframe": None})
