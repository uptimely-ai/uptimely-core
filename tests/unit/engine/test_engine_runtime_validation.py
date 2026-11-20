import collections.abc
import copy
import logging
import pathlib
import types

import polars as pl
import pytest
from support import execution as execution_support

from uptimely import engine as uptimely_engine
from uptimely import plan as uptimely_plan
from uptimely.codebase.python import entrypoint as entrypoint_module
from uptimely.engine.dataframe import backend as backend_module
from uptimely.engine.dataframe import fragment as fragment_module
from uptimely.engine.runtime import execution as execution_module
from uptimely.engine.runtime import state as state_module
from uptimely.library.merge import polars as merge_module

PLAN_PATH = pathlib.Path(__file__).parents[2] / "fixtures" / "plans" / "simple_engine.json"


def _plan() -> uptimely_plan.ExecutionPlan:
    return uptimely_plan.from_json(PLAN_PATH)


def _patch_callables(monkeypatch: pytest.MonkeyPatch, callables: dict[str, object]) -> None:
    def merge_by_grain_entrypoint(
        dataset: merge_module.DataFrame | None,
        fragment: merge_module.DataFrame,
        dataset_identifiers: collections.abc.Sequence[str],
        fragment_keys: collections.abc.Sequence[str] | None = None,
        *,
        key_columns: collections.abc.Sequence[str] = (),
        join_cardinality: str = "m:m",
        broadcast_cardinality: str = "m:m",
    ) -> merge_module.DataFrame:
        return merge_module.merge_by_grain(
            dataset,
            fragment,
            dataset_identifiers,
            fragment_keys,
            key_columns=key_columns,
            join_cardinality=join_cardinality,
            broadcast_cardinality=broadcast_cardinality,
        )

    callables = {
        "uptimely.library.merge.polars:merge_by_grain": merge_by_grain_entrypoint,
        **callables,
    }

    class _TestEntrypoint:
        def __init__(
            self, location: str, package: entrypoint_module.PackageOrigin | None = None
        ) -> None:
            self.location = location
            self.package = package
            self.module = types.SimpleNamespace(location=location.split(":", 1)[0])

        @property
        def function(self) -> object:
            return self

        def load(self) -> object:
            return callables[self.location]

    monkeypatch.setattr(entrypoint_module, "Entrypoint", _TestEntrypoint)


def test_input_validation_reads_each_dataset_schema_once(
    monkeypatch: pytest.MonkeyPatch, engine_for_plan: execution_support.EngineFactory
) -> None:
    engine = engine_for_plan(_plan())
    state = state_module.RuntimeState(
        datasets={
            "telemetry": execution_support.dataset(pl.DataFrame({"asset_id": ["A"]})),
            "source": execution_support.dataset(
                pl.DataFrame({"asset_id": ["A"], "reading": [1], "other": [2]})
            ),
        }
    )
    column_names = engine.backend.column_names
    inspected: list[object] = []

    def inspect(frame: object) -> list[str]:
        inspected.append(frame)
        return column_names(frame)

    monkeypatch.setattr(engine.backend, "column_names", inspect)
    executor = execution_module.InvocationExecutor(
        engine.backend, {}, engine.parameters, state, validate=True
    )
    invocation = copy.replace(
        engine.plan.invocations[1], input_features=["asset_id", "reading", "other"]
    )

    executor.check_input_requirements(invocation)

    assert len(inspected) == 2
    assert inspected[0] is state.datasets["telemetry"].dataframe
    assert inspected[1] is state.datasets["source"].dataframe


@pytest.mark.parametrize(
    ("invalid", "message", "check_count"),
    [
        ("no_argument", "exactly one foreign dataframe argument", 1),
        ("multiple_arguments", "exactly one foreign dataframe argument", 1),
        ("non_reference", "must reference a foreign source profile", 2),
        ("target_reference", "must reference a foreign source profile", 2),
        ("missing_source", "Profile dataframe is unavailable: missing", 3),
        ("missing_feature", "input feature is unavailable in foreign source profile", 4),
        (None, None, 4),
    ],
)
def test_foreign_input_validation_runs_atomic_checks_in_fail_fast_order(
    caplog: pytest.LogCaptureFixture,
    invalid: str | None,
    message: str | None,
    check_count: int,
) -> None:
    caplog.set_level(logging.DEBUG, logger=execution_module.__name__)
    invocation = copy.replace(
        _plan().invocations[1],
        dataframe_input_scope="foreign",
        argument_types={"source": "dataframe"},
        arguments={"source": "source"},
        input_features=["reading"],
    )
    if invalid == "no_argument":
        invocation.argument_types.clear()
    elif invalid == "multiple_arguments":
        invocation.argument_types["other"] = "dataframe"
    elif invalid == "non_reference":
        invocation.arguments["source"] = 1
    elif invalid == "target_reference":
        invocation.arguments["source"] = invocation.profile_id
    elif invalid == "missing_source":
        invocation.arguments["source"] = "missing"
    elif invalid == "missing_feature":
        invocation.input_features[:] = ["missing"]
    state = state_module.RuntimeState(
        datasets={"source": execution_support.dataset(pl.DataFrame({"reading": [1]}))}
    )
    executor = execution_module.InvocationExecutor(
        backend_module.PolarsBackend(), {}, {}, state, validate=True
    )

    if message is None:
        executor.check_input_requirements(invocation)
    else:
        with pytest.raises(ValueError, match=message):
            executor.check_input_requirements(invocation)

    assert (
        caplog.messages
        == [
            "Check foreign dataframe argument",
            "Check foreign source reference",
            "Check foreign source availability",
            "Check foreign input features",
        ][:check_count]
    )


@pytest.mark.parametrize("sources", [0, 2])
def test_input_validation_rejects_missing_or_ambiguous_foreign_features(
    sources: int, engine_for_plan: execution_support.EngineFactory
) -> None:
    engine = engine_for_plan(_plan())
    state = state_module.RuntimeState(
        datasets={
            f"source_{index}": execution_support.dataset(pl.DataFrame({"reading": [index]}))
            for index in range(sources)
        }
    )
    executor = execution_module.InvocationExecutor(
        engine.backend, {}, engine.parameters, state, validate=True
    )

    with pytest.raises(ValueError, match="input feature is unavailable or ambiguous: reading"):
        executor.check_input_requirements(engine.plan.invocations[1])


def test_runtime_state_prefers_dataset_to_fragment_lookup() -> None:
    dataset = pl.DataFrame({"asset_id": ["dataset"]})
    fragment = pl.DataFrame({"asset_id": ["fragment"]})
    main = execution_support.dataset(dataset)
    main.fragments["shared"] = fragment_module.Fragment(fragment, ())
    state = state_module.RuntimeState(datasets={"shared": main})

    assert state.resolve_dataset_or_fragment_dataframe("shared") is dataset


def test_runtime_state_is_not_shared_between_instances() -> None:
    first = state_module.RuntimeState()
    second = state_module.RuntimeState()
    first.datasets["telemetry"] = execution_support.dataset(pl.DataFrame({"asset_id": ["A"]}))

    assert second.datasets == {}


def test_vectorize_requires_an_accumulated_target() -> None:
    executor = execution_module.InvocationExecutor(
        backend_module.PolarsBackend(),
        {},
        {},
        state_module.RuntimeState(),
    )
    invocation = uptimely_plan.Invocation(
        id="vectorize",
        role="compute",
        result="target",
        dataframe_input_scope="target",
        entrypoint="test:calculate",
        function_id="calculate",
        operator_id="calculate",
        profile_id="telemetry",
    )

    with pytest.raises(ValueError, match="Profile dataframe is unavailable: telemetry"):
        executor.execute(invocation)


def test_column_projection_failure_preserves_published_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = pl.DataFrame({"reading": [3]})
    dataset = execution_support.dataset(original)
    state = state_module.RuntimeState(datasets={"telemetry": dataset})
    adapter = backend_module.PolarsBackend()
    executor = execution_module.InvocationExecutor(adapter, {}, {}, state)
    invocation = uptimely_plan.Invocation(
        id="vectorize",
        role="compute",
        result="target",
        dataframe_input_scope="target",
        entrypoint="test:calculate",
        function_id="calculate",
        operator_id="calculate",
        profile_id="telemetry",
        output_features=["first", "second"],
    )
    result = original.with_columns(pl.lit(4).alias("first"), pl.lit(6).alias("second"))

    def invoke(invocation: uptimely_plan.Invocation) -> pl.DataFrame:
        return result

    select = adapter.select

    def select_output(frame: object, columns: list[str]) -> object:
        if "second" in columns:
            raise ValueError("Cannot project second output")
        return select(frame, columns)

    monkeypatch.setattr(executor, "_invoke", invoke)
    monkeypatch.setattr(adapter, "select", select_output)

    with pytest.raises(ValueError, match="Cannot project second output"):
        executor.execute(invocation)

    assert dataset.dataframe is original
    assert state.calculated_outputs == {}
    assert dataset.fragments == {}


@pytest.mark.parametrize("validate", [False, True])
@pytest.mark.parametrize("reverse", [False, True])
def test_vectorize_validation_uses_one_lazy_input_snapshot(
    monkeypatch: pytest.MonkeyPatch, validate: bool, reverse: bool
) -> None:
    collections = 0
    calls = 0

    def alternating_order(frame: pl.DataFrame) -> pl.DataFrame:
        nonlocal collections
        collections += 1
        return frame.reverse() if collections % 2 else frame

    original = (
        pl.DataFrame({"key": ["A", "B"], "value": [1, 2]})
        .lazy()
        .map_batches(
            alternating_order,
            predicate_pushdown=False,
            projection_pushdown=False,
            slice_pushdown=False,
        )
    )
    dataset = execution_support.dataset(original)
    state = state_module.RuntimeState(datasets={"dataset": dataset})
    executor = execution_module.InvocationExecutor(
        backend_module.PolarsBackend(), {}, {}, state, validate=validate
    )

    def calculate(dataset: pl.LazyFrame) -> pl.LazyFrame:
        nonlocal calls
        calls += 1
        assert isinstance(dataset, pl.LazyFrame)
        result = dataset.with_columns((pl.col("value") * 2).alias("doubled"))
        return result.reverse() if reverse else result

    _patch_callables(monkeypatch, {"test:calculate": calculate})
    invocation = uptimely_plan.Invocation(
        id="vectorize",
        role="compute",
        result="target",
        dataframe_input_scope="target",
        entrypoint="test:calculate",
        function_id="calculate",
        operator_id="calculate",
        profile_id="dataset",
        target_identifiers=["key"],
        output_features=["doubled"],
        row_order_relation="preserve",
        existing_data_relation="preserve",
        arguments={"dataset": "dataset"},
        argument_types={"dataset": "dataframe"},
    )

    if validate and reverse:
        with pytest.raises(ValueError, match="preserve existing column values and row order"):
            executor.execute(invocation)
        assert dataset.dataframe is original
        assert state.calculated_outputs == {}
    else:
        executor.execute(invocation)
        assert isinstance(dataset.dataframe, pl.LazyFrame)
        assert ("dataset", "doubled") in state.calculated_outputs
    assert calls == 1
    assert collections == (1 if validate else 0)


def test_execute_rejects_scalar_calculations(
    monkeypatch: pytest.MonkeyPatch, engine_for_plan: execution_support.EngineFactory
) -> None:
    def read(source: str) -> pl.DataFrame:
        return pl.DataFrame({"asset_id": ["A"], "reading": [2]})

    def constant(column: str, dataset: pl.DataFrame) -> int:
        return 10

    _patch_callables(
        monkeypatch,
        {"test:read": read, "test:double": constant, "test:write": lambda **_: None},
    )
    engine = engine_for_plan(_plan(), {"source": "/tmp/telemetry.parquet"})

    result = engine.run(validate=True)

    assert "must be a Polars DataFrame or LazyFrame" in next(iter(result.failures.values()))


def test_vectorize_mapping_emits_multiple_features_with_one_call(
    monkeypatch: pytest.MonkeyPatch, engine_for_plan: execution_support.EngineFactory
) -> None:
    calls = 0

    def read() -> pl.DataFrame:
        return pl.DataFrame({"asset_id": ["A"], "reading": [3]})

    def calculate(dataset: pl.DataFrame) -> pl.DataFrame:
        nonlocal calls
        calls += 1
        return dataset.with_columns(
            (pl.col("reading") + 1).alias("reading_plus_one"),
            (pl.col("reading") * 2).alias("reading_times_two"),
        )

    computed_function_ids: list[str] = []
    compute_fragment = fragment_module.Fragment.compute
    merge_calls = 0
    merge_by_grain = merge_module.merge_by_grain

    def compute_spy(backend: object, invocation: object, load: object, **kwargs: object) -> object:
        computed_function_ids.append(invocation.function_id)
        return compute_fragment(backend, invocation, load, **kwargs)

    def merge_spy(*args: object, **kwargs: object) -> object:
        nonlocal merge_calls
        merge_calls += 1
        return merge_by_grain(*args, **kwargs)

    read_invocation = uptimely_plan.Invocation(
        id="invocation:read:load:asset:telemetry:load",
        role="compute",
        result="fragment",
        fragment_dimensions="target",
        entrypoint="test:read",
        function_id="load",
        operator_id="load",
        profile_id="telemetry",
        output_features=["asset_id", "reading"],
    )
    merge_invocation = uptimely_plan.Invocation(
        id="invocation:merge:merge_by_grain:asset:telemetry:load",
        role="merge",
        result="target",
        entrypoint="uptimely.library.merge.polars:merge_by_grain",
        function_id="merge_by_grain",
        operator_id="load",
        profile_id="telemetry",
        output_features=[],
        input_features=[],
        arguments={
            "dataset": "telemetry",
            "fragment": "$operators.@.fragment",
            "dataset_identifiers": ["asset_id"],
        },
        dependency_ids=[read_invocation.id],
        target_identifiers=["asset_id"],
        column_types={},
        argument_types={
            "dataset": "dataframe | null",
            "fragment": "dataframe",
            "dataset_identifiers": "array[string]",
        },
    )
    vectorize_invocation = uptimely_plan.Invocation(
        id="invocation:vectorize:calculate:asset:telemetry:reading_plus_one",
        role="compute",
        result="target",
        dataframe_input_scope="target",
        entrypoint="test:calculate",
        function_id="calculate",
        operator_id="reading_plus_one",
        profile_id="telemetry",
        output_features=["reading_plus_one", "reading_times_two"],
        arguments={"dataset": "telemetry"},
        argument_types={"dataset": "dataframe"},
        dependency_ids=[merge_invocation.id],
    )
    plan = uptimely_plan.ExecutionPlan(
        plan_version=uptimely_plan.PLAN_VERSION,
        required_backend="polars",
        invocations=[read_invocation, merge_invocation, vectorize_invocation],
        stages=[[read_invocation.id], [merge_invocation.id], [vectorize_invocation.id]],
    )
    _patch_callables(monkeypatch, {"test:read": read, "test:calculate": calculate})
    monkeypatch.setattr(fragment_module.Fragment, "compute", staticmethod(compute_spy))
    monkeypatch.setattr(merge_module, "merge_by_grain", merge_spy)
    engine = engine_for_plan(plan)

    result = engine.run()

    assert result.failures == {}
    assert calls == 1
    assert result.datasets["telemetry"]["reading"].to_list() == [3]
    assert result.datasets["telemetry"].select("reading_plus_one", "reading_times_two").rows() == [
        (4, 6)
    ]
    assert computed_function_ids == ["load"]
    assert merge_calls == 1
    assert set(result.calculated_outputs) == {
        ("telemetry", "reading_plus_one"),
        ("telemetry", "reading_times_two"),
    }


@pytest.mark.parametrize("batch_size", [0, -1, True, "100"])
def test_engine_config_rejects_invalid_batch_size(batch_size: object) -> None:
    with pytest.raises(ValueError, match="batch_size"):
        uptimely_engine.EngineBackendConfig(batch_size=batch_size)


@pytest.mark.parametrize("dataframe", ["pandas", ""])
def test_engine_config_rejects_unsupported_dataframe_backend(
    dataframe: object, bundle_for_plan: execution_support.BundleFactory
) -> None:
    configuration = uptimely_engine.EngineConfig(backend={"dataframe": dataframe})
    with pytest.raises(ValueError, match="Unsupported dataframe backend"):
        uptimely_engine.Engine(bundle_for_plan(_plan()), configuration)


def test_engine_config_rejects_non_string_dataframe_backend() -> None:
    with pytest.raises(ValueError, match="dataframe"):
        uptimely_engine.EngineConfig(backend={"dataframe": None})
