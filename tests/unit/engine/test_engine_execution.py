import collections.abc
import copy
import logging
import pathlib
import types

import polars as pl
import pytest
from support import execution as execution_support

from uptimely import compiler as uptimely_compiler
from uptimely import engine as uptimely_engine
from uptimely import plan as uptimely_plan
from uptimely.codebase.python import entrypoint as entrypoint_module
from uptimely.engine.dataframe import backend as backend_module
from uptimely.engine.dataframe import dataset as dataset_module
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


@pytest.mark.parametrize("dimensionless", [False, True])
def test_engine_preserves_lazy_outputs_and_collects_bounded_previews(
    monkeypatch: pytest.MonkeyPatch,
    dimensionless: bool,
    bundle_for_plan: execution_support.BundleFactory,
) -> None:
    def read(source: str) -> pl.LazyFrame:
        return pl.DataFrame({"asset_id": ["A"], "reading": [2]}).lazy()

    def double(column: str, dataset: pl.LazyFrame) -> pl.LazyFrame:
        return dataset.with_columns((pl.col(column) * 2).alias("doubled"))

    def write(dataset: pl.LazyFrame, features: list[str]) -> None:
        assert isinstance(dataset, pl.LazyFrame)

    collected_heights: list[int] = []
    original_collect = pl.LazyFrame.collect

    def collect(frame: pl.LazyFrame, *args: object, **kwargs: object) -> pl.DataFrame:
        sample = original_collect(frame, *args, **kwargs)
        collected_heights.append(sample.height)
        return sample

    _patch_callables(monkeypatch, {"test:read": read, "test:double": double, "test:write": write})
    bundle = bundle_for_plan(_plan())
    if dimensionless:
        bundle = copy.replace(
            bundle,
            execution_plan=copy.replace(
                bundle.execution_plan,
                invocations=[
                    copy.replace(
                        invocation,
                        target_identifiers=[],
                        arguments=(
                            invocation.arguments | {"dataset_identifiers": []}
                            if invocation.role == "merge"
                            else invocation.arguments
                        ),
                    )
                    for invocation in bundle.execution_plan.invocations
                ],
            ),
        )
    engine = uptimely_engine.Engine(
        bundle,
        uptimely_engine.EngineConfig(),
        {"source": "/tmp/telemetry.parquet"},
    )
    monkeypatch.setattr(pl.LazyFrame, "collect", collect)

    result = engine.run()

    assert not result.failures
    assert set(result.invocation_statuses.values()) == {"succeeded"}
    assert isinstance(result.datasets["telemetry"], pl.LazyFrame)
    assert collected_heights == [1]
    assert result.preview_frames["telemetry"].height == 1


@pytest.mark.parametrize(
    ("invalid", "message"),
    [
        ("key", "missing identifier columns"),
        ("output", "missing output columns"),
        ("type", "expected string"),
    ],
)
def test_validation_flag_checks_lazy_schema(
    monkeypatch: pytest.MonkeyPatch,
    invalid: str,
    message: str,
    bundle_for_plan: execution_support.BundleFactory,
) -> None:
    def read(source: str) -> pl.LazyFrame:
        frame = pl.DataFrame({"asset_id": ["A"], "reading": [2]}).lazy()
        if invalid == "key":
            frame = frame.drop("asset_id")
        elif invalid == "output":
            frame = frame.drop("reading")
        else:
            frame = frame.with_columns(pl.lit(1).alias("asset_id"))
        return frame

    _patch_callables(monkeypatch, {"test:read": read})
    engine = uptimely_engine.Engine(
        bundle_for_plan(_plan()),
        uptimely_engine.EngineConfig(),
        {"source": "/tmp/telemetry.parquet"},
    )
    result = engine.run(validate=True)

    assert message in next(iter(result.failures.values()))
    assert not result.datasets


def test_unsupported_feature_type_is_reported_in_warning(
    monkeypatch: pytest.MonkeyPatch,
    engine_for_plan: execution_support.EngineFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="uptimely.engine")
    plan = _plan()
    read = next(item for item in plan.invocations if item.result == "fragment")
    read.column_types["reading"] = "floatti"
    _patch_callables(
        monkeypatch,
        {"test:read": lambda source: pl.DataFrame({"asset_id": ["A"], "reading": [1]})},
    )

    engine_for_plan(plan, {"source": "/tmp/input"}).run(validate=True)

    warning = next(message for message in caplog.messages if message.startswith("Invocation "))
    assert warning == (
        "Invocation invocation:read:load:telemetry:reading failed: "
        "Unsupported feature type for reading: floatti. "
        "Supported types: string, integer, float, numeric, boolean, datetime, date, object, array"
    )


@pytest.mark.parametrize("lazy", [False, True])
@pytest.mark.parametrize("invalid", ["duplicates", "types", "row_count", "keys"])
def test_validation_is_opt_in_for_eager_and_lazy_frames(
    monkeypatch: pytest.MonkeyPatch,
    engine_for_plan: execution_support.EngineFactory,
    lazy: bool,
    invalid: str,
) -> None:
    writes: list[object] = []

    def read(source: str) -> pl.DataFrame | pl.LazyFrame:
        keys: list[str] | list[int] = ["A", "A"] if invalid == "duplicates" else ["A", "B"]
        if invalid == "types":
            keys = [1, 2]
        frame = pl.DataFrame({"asset_id": keys, "reading": [2, 3]})
        return frame.lazy() if lazy else frame

    def double(column: str, dataset: pl.DataFrame | pl.LazyFrame) -> pl.DataFrame | pl.LazyFrame:
        frame = dataset.with_columns((pl.col(column) * 2).alias("doubled"))
        if invalid == "row_count":
            frame = frame.head(1)
        if invalid == "keys":
            frame = frame.with_columns(pl.col("asset_id") + "_changed")
        return frame

    def write(dataset: object, features: list[str]) -> None:
        writes.append(dataset)

    _patch_callables(monkeypatch, {"test:read": read, "test:double": double, "test:write": write})
    runtime = engine_for_plan(_plan(), {"source": "/tmp/input"})

    unchecked = runtime.run()
    assert not unchecked.failures
    assert len(writes) == 1
    frame = unchecked.datasets["telemetry"]
    if lazy:
        frame.collect()

    checked = runtime.run(validate=True)
    message = {
        "duplicates": "duplicate identifiers",
        "types": "expected string",
        "row_count": "must preserve existing column values and row order",
        "keys": "must preserve existing column values and row order",
    }[invalid]
    assert message in next(iter(checked.failures.values()))
    assert len(writes) == 1
    assert "skipped" in checked.invocation_statuses.values()


def test_default_execution_skips_expensive_fragment_validation(
    monkeypatch: pytest.MonkeyPatch, engine_for_plan: execution_support.EngineFactory
) -> None:
    def unexpected_content_check(*_args: object, **_kwargs: object) -> None:
        pytest.fail(
            f"Default execution called an optional fragment content check: {_args!r}, {_kwargs!r}"
        )

    frame = pl.DataFrame({"asset_id": ["A"], "reading": [2], "doubled": [4]})
    _patch_callables(
        monkeypatch,
        {
            "test:read": lambda **_: frame,
            "test:double": lambda **_: frame,
            "test:write": lambda **_: None,
        },
    )
    monkeypatch.setattr(
        execution_module.InvocationExecutor,
        "check_input_requirements",
        unexpected_content_check,
    )
    for method in ("row_count", "is_duplicated", "same_keys", "validate_types"):
        monkeypatch.setattr(backend_module.PolarsBackend, method, unexpected_content_check)
    monkeypatch.setattr(
        dataset_module.Dataset,
        "validate_accumulated_frame",
        unexpected_content_check,
    )

    result = engine_for_plan(_plan(), {"source": "/tmp/input"}).run()

    assert not result.failures
    assert set(result.invocation_statuses.values()) == {"succeeded"}


@pytest.mark.parametrize("validate", [False, True])
def test_executor_reuses_dataset_main_frame_and_retains_projected_fragments(
    monkeypatch: pytest.MonkeyPatch,
    engine_for_plan: execution_support.EngineFactory,
    validate: bool,
) -> None:
    raw_source = pl.DataFrame({"asset_id": ["A"], "reading": [2], "extra": [0]})

    def double(column: str, dataset: pl.DataFrame) -> pl.DataFrame:
        assert isinstance(dataset, pl.DataFrame)
        assert "extra" not in dataset.columns
        return dataset.with_columns((pl.col(column) * 2).alias("doubled"))

    _patch_callables(monkeypatch, {"test:read": lambda **_: raw_source, "test:double": double})
    engine = engine_for_plan(_plan(), {"source": "/tmp/input"})
    state = state_module.RuntimeState()
    executor = execution_module.InvocationExecutor(
        engine.backend,
        {},
        engine.parameters,
        state,
        validate=validate,
    )
    read = next(item for item in engine.plan.invocations if item.result == "fragment")
    merge = next(item for item in engine.plan.invocations if item.role == "merge")
    calculate = next(
        item for item in engine.plan.invocations if item.dataframe_input_scope == "target"
    )

    executor.execute(read)
    assert state.datasets == {}
    assert set(state.computed_fragments) == {read.id}
    executor.execute(merge)
    main = state.datasets["telemetry"]
    source = main.fragments[read.operator_id]
    assert main.identifiers == ("asset_id",)
    assert source.dataframe.columns == ["asset_id", "reading"]

    executor.execute(calculate)

    assert state.datasets["telemetry"] is main
    assert main.dataframe["doubled"].to_list() == [4]
    assert "doubled" not in source.dataframe.columns
    assert "extra" in raw_source.columns
    assert state.resolve_dataset_or_fragment_dataframe("telemetry") is main.dataframe
    assert executor.bindings.resolve_value("telemetry", "dataframe") is main.dataframe
    assert executor.validate is validate


def test_saved_plan_executes_without_compiler(
    monkeypatch: pytest.MonkeyPatch, engine_for_plan: execution_support.EngineFactory
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
    engine = engine_for_plan(saved_plan, {"source": "/tmp/telemetry.parquet"})

    result = engine.run()

    assert result.failures == {}
    assert result.datasets["telemetry"]["doubled"].to_list() == [4, 6]


def test_engine_reports_package_provenance_without_enforcing_versions(
    monkeypatch: pytest.MonkeyPatch, engine_for_plan: execution_support.EngineFactory
) -> None:
    engine = engine_for_plan(_plan())
    runtime_package = entrypoint_module.PackageOrigin("runtime-package", "2.0")
    monkeypatch.setattr(
        entrypoint_module.PackageOrigin,
        "read",
        lambda _module: runtime_package,
    )
    executor = execution_module.InvocationExecutor(
        engine.backend,
        {
            location: entrypoint_module.Entrypoint(
                location,
                package=entrypoint_module.PackageOrigin("recorded-package", "1.0"),
            )
            for location in (
                "uptimely.codebase.python.entrypoint:PackageOrigin",
                "math:pi",
            )
        },
        engine.parameters,
        state_module.RuntimeState(),
    )

    invocation = copy.replace(
        engine.plan.invocations[0],
        entrypoint="uptimely.codebase.python.entrypoint:PackageOrigin",
        arguments={"distribution": "recorded-package", "version": "1.0"},
    )

    assert executor._invoke(invocation) == entrypoint_module.PackageOrigin(
        "recorded-package", "1.0"
    )
    incompatible = copy.replace(invocation, entrypoint="math:pi", arguments={})
    with pytest.raises(
        ValueError,
        match="recorded-package.*available runtime package: runtime-package==2.0",
    ):
        executor._invoke(incompatible)


def test_executor_validates_inputs_against_current_runtime_state(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=execution_module.__name__)
    runtime_state = state_module.RuntimeState(
        datasets={
            "dataset": execution_support.dataset(pl.DataFrame({"local": [1]})),
            "first": execution_support.dataset(pl.DataFrame({"shared": [1], "unique": [1]})),
            "second": execution_support.dataset(pl.DataFrame({"shared": [1]})),
        }
    )
    executor = execution_module.InvocationExecutor(
        backend_module.PolarsBackend(),
        {},
        {},
        runtime_state,
        validate=True,
    )
    invocation = uptimely_plan.Invocation(
        id="invocation",
        role="compute",
        result="target",
        dataframe_input_scope="target",
        entrypoint="test:calculate",
        function_id="calculate",
        operator_id="calculate",
        profile_id="dataset",
        input_features=["local"],
    )

    executor.check_input_requirements(invocation)
    invocation.input_features[:] = ["unique"]
    executor.check_input_requirements(invocation)
    invocation.input_features[:] = ["shared"]
    with pytest.raises(ValueError, match="unavailable or ambiguous: shared"):
        executor.check_input_requirements(invocation)
    runtime_state.datasets["dataset"].dataframe = pl.DataFrame({"new": [1]})
    del runtime_state.datasets["second"]
    invocation.input_features[:] = ["new"]
    executor.check_input_requirements(invocation)
    invocation.input_features[:] = ["shared"]
    executor.check_input_requirements(invocation)
    assert caplog.messages == ["Check declared input features"] * 5


def test_engine_entrypoints_include_saved_package_provenance(
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    original = _plan()
    saved_plan = copy.replace(
        original,
        invocations=[
            copy.replace(
                original.invocations[0],
                package=uptimely_plan.Package(
                    distribution="recorded-package",
                    version="1.0",
                ),
            ),
            *original.invocations[1:],
        ],
    )
    engine = engine_for_plan(saved_plan, {"source": "/tmp/input.parquet"})

    result = engine.run()

    assert result.invocation_statuses[saved_plan.invocations[0].id] == "failed"
    assert (
        "recorded package provenance: recorded-package==1.0"
        in result.failures[saved_plan.invocations[0].id]
    )


def test_repeated_execution_does_not_leak_runtime_state(
    monkeypatch: pytest.MonkeyPatch, engine_for_plan: execution_support.EngineFactory
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
    engine = engine_for_plan(_plan(), {"source": "/tmp/telemetry.parquet"})

    first_result = engine.run()
    second_result = engine.run()

    assert first_result.failures == second_result.failures == {}
    assert first_result.datasets is not second_result.datasets
    assert first_result.calculated_outputs is not second_result.calculated_outputs
    assert first_result.datasets["telemetry"]["doubled"].to_list() == [2, 4]
    assert second_result.datasets["telemetry"]["doubled"].to_list() == [4, 6]
    first_output = first_result.calculated_outputs["telemetry", "doubled"]
    assert first_output["doubled"].to_list() == [2, 4]


def test_execute_stops_after_a_failed_operation(
    monkeypatch: pytest.MonkeyPatch, engine_for_plan: execution_support.EngineFactory
) -> None:
    called = False

    def read(source: str) -> pl.DataFrame:
        raise RuntimeError("source unavailable")

    def write(dataset: object, features: list[str]) -> None:
        nonlocal called
        called = True

    _patch_callables(monkeypatch, {"test:read": read, "test:write": write})
    engine = engine_for_plan(_plan(), {"source": "/tmp/telemetry.parquet"})

    result = engine.run()

    read_id = "invocation:read:load:telemetry:reading"
    write_id = "invocation:write:save:telemetry:doubled"
    assert result.invocation_statuses[read_id] == "failed"
    assert "source unavailable" in result.failures[read_id]
    assert result.invocation_statuses[write_id] == "skipped"
    assert result.invocation_statuses == {
        invocation.id: "failed" if invocation.id == read_id else "skipped"
        for invocation in engine.plan.invocations
    }
    assert set(result.durations) == {read_id}
    assert called is False
