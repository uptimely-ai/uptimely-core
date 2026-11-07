import copy
import logging
import pathlib
import types

import polars as pl
import pytest
from support import execution as execution_support

from uptimely import compiler as uptimely_compiler
from uptimely import engine as uptimely_engine
from uptimely import entrypoint as entrypoint_module
from uptimely import plan as uptimely_plan
from uptimely import spec
from uptimely.engine.dataframe import backend as backend_module
from uptimely.engine.dataframe import dataset as dataset_module
from uptimely.engine.dataframe import fragment as fragment_module
from uptimely.engine.runtime import bindings as bindings_module
from uptimely.engine.runtime import execution as execution_module
from uptimely.engine.runtime import state as state_module
from uptimely.library.merge import polars as merge_module
from uptimely.plan import serialization as plan_serialization
from uptimely.spec.python import assembly, dimension, profile, ref

PLAN_PATH = pathlib.Path(__file__).parents[2] / "fixtures" / "plans" / "simple_engine.json"


def _plan() -> uptimely_plan.ExecutionPlan:
    return uptimely_plan.from_json(PLAN_PATH)


def _patch_callables(monkeypatch: pytest.MonkeyPatch, callables: dict[str, object]) -> None:
    def merge_by_grain_entrypoint(*args: object, **kwargs: object) -> object:
        return merge_module.merge_by_grain(*args, **kwargs)

    callables = {
        "uptimely.library.merge.polars:merge_by_grain": merge_by_grain_entrypoint,
        **callables,
    }

    class _TestEntrypoint:
        def __init__(
            self, location: str, package: entrypoint_module.PackageProvenance | None = None
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


@pytest.mark.parametrize("validate", [False, True])
def test_execute_runs_stages_and_returns_runtime_outputs(
    monkeypatch: pytest.MonkeyPatch,
    engine_for_plan: execution_support.EngineFactory,
    validate: bool,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="uptimely.engine")
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
    engine = engine_for_plan(_plan(), {"source": "/tmp/telemetry.parquet"})

    result = engine.run(validate=validate)

    assert set(result.invocation_statuses.values()) == {"succeeded"}
    assert result.failures == {}
    assert result.plan_version == 6
    assert not hasattr(result, "datasets")
    assert isinstance(result.calculated_outputs["telemetry", "doubled"], pl.DataFrame)
    assert set(result.main_frames) == {"telemetry"}
    assert result.main_frames["telemetry"].select("doubled").to_series().to_list() == [
        4,
        6,
    ]
    assert written["features"] == ["doubled"]
    assert written["dataset"].select("asset_id", "doubled").rows() == [("A", 4), ("B", 6)]
    headings = [message for message in caplog.messages if message.startswith("\nInvocation: ")]
    assert headings == [
        f"\nInvocation: {invocation.operator_id} [{invocation.function_kind}]"
        for invocation in engine.plan.execution_invocations
    ]
    assert caplog.messages.count("  Merge:\n    Target profile: telemetry") == 1
    assert [message for message in caplog.messages if message.startswith("  Function: ")] == [
        "  Function: load",
        "  Function: __uptimely_merge_by_grain",
        "  Function: double",
        "  Function: save",
    ]
    assert "  Fragment:" in caplog.messages


@pytest.mark.parametrize("merge_failure", [None, "exception", "incomplete"])
def test_custom_merges_receive_staged_fragment_and_publish_only_on_success(
    monkeypatch: pytest.MonkeyPatch,
    engine_for_plan: execution_support.EngineFactory,
    merge_failure: str | None,
) -> None:
    merge_inputs: list[tuple[list[str] | None, list[str]]] = []

    def read_first() -> pl.DataFrame:
        return pl.DataFrame({"id": ["A"], "first": [1]})

    def read_second() -> pl.DataFrame:
        return pl.DataFrame({"id": ["A"], "second": [2]})

    def custom_merge(
        target: pl.DataFrame | None,
        fragment: pl.DataFrame,
        target_keys: list[str],
    ) -> pl.DataFrame:
        merge_inputs.append((target.columns if target is not None else None, fragment.columns))
        if target is not None and merge_failure == "exception":
            raise RuntimeError("custom merge failed")
        if target is not None and merge_failure == "incomplete":
            return fragment
        return merge_module.merge_by_grain(target, fragment, target_keys)

    def write(dataset: pl.DataFrame) -> None:
        assert dataset.columns == ["id", "first", "second"]

    read_first_id = "read-first"
    merge_first_id = "merge-first"
    read_second_id = "read-second"
    merge_second_id = "merge-second"
    write_id = "write"
    reads = [
        uptimely_plan.Invocation(
            id=read_first_id,
            function_kind="read",
            entrypoint="test:read_first",
            function_id="read_first",
            operator_id="first",
            dataset_id="telemetry",
            output_features=["id", "first"],
            id_columns=["id"],
        ),
        uptimely_plan.Invocation(
            id=read_second_id,
            function_kind="read",
            entrypoint="test:read_second",
            function_id="read_second",
            operator_id="second",
            dataset_id="telemetry",
            output_features=["id", "second"],
            id_columns=["id"],
        ),
    ]

    def merge_invocation(
        invocation_id: str, operator_id: str, compute_id: str, dependencies: list[str]
    ) -> uptimely_plan.Invocation:
        return uptimely_plan.Invocation(
            id=invocation_id,
            function_kind="merge",
            entrypoint="test:custom_merge",
            function_id="custom_merge",
            operator_id=operator_id,
            dataset_id="telemetry",
            arguments={
                "target": "telemetry",
                "fragment": "$operators.@.fragment",
                "target_keys": ["id"],
            },
            dependency_ids=[compute_id, *dependencies],
            id_columns=["id"],
            argument_types={
                "target": "dataframe | null",
                "fragment": "dataframe",
                "target_keys": "array[string]",
            },
        )

    first_merge = merge_invocation(merge_first_id, "first", read_first_id, [])
    second_merge = merge_invocation(merge_second_id, "second", read_second_id, [merge_first_id])
    writer = uptimely_plan.Invocation(
        id=write_id,
        function_kind="write",
        entrypoint="test:write",
        function_id="write",
        operator_id="write",
        dataset_id="telemetry",
        arguments={"dataset": "telemetry"},
        dependency_ids=[merge_second_id],
        argument_types={"dataset": "dataframe"},
    )
    plan = uptimely_plan.ExecutionPlan(
        plan_version=6,
        required_backend="polars",
        resources={
            "dimensions": {"id": {"resolutions": {"id": {"key": "id", "type": "string"}}}},
            "profiles": {"telemetry": {"grain": [{"dimension": "id", "resolution": "id"}]}},
            "functions": {
                "read_first": {"kind": "read", "returns": "dataframe", "args": {}},
                "read_second": {"kind": "read", "returns": "dataframe", "args": {}},
                "custom_merge": {
                    "kind": "merge",
                    "returns": "dataframe",
                    "args": {
                        "target": {"type": "dataframe | null"},
                        "fragment": {"type": "dataframe"},
                        "target_keys": {"type": "array[string]"},
                    },
                },
                "write": {
                    "kind": "write",
                    "returns": "none",
                    "args": {"dataset": {"type": "dataframe"}},
                },
            },
        },
        invocations=[*reads, first_merge, second_merge, writer],
        stages=[
            [read_first_id],
            [merge_first_id],
            [read_second_id],
            [merge_second_id],
            [write_id],
        ],
    )
    _patch_callables(
        monkeypatch,
        {
            "test:read_first": read_first,
            "test:read_second": read_second,
            "test:custom_merge": custom_merge,
            "test:write": write,
        },
    )

    result = engine_for_plan(plan).run()

    assert merge_inputs == [
        (None, ["id", "first"]),
        (["id", "first"], ["id", "second"]),
    ]
    assert result.invocation_statuses[read_first_id] == "succeeded"
    assert result.invocation_statuses[merge_first_id] == "succeeded"
    assert result.invocation_statuses[read_second_id] == "succeeded"
    if merge_failure is not None:
        assert result.invocation_statuses[merge_second_id] == "failed"
        assert result.invocation_statuses[write_id] == "skipped"
        if merge_failure == "exception":
            assert result.failures[merge_second_id] == "custom merge failed"
        else:
            assert "missing required columns: first" in result.failures[merge_second_id]
        assert result.main_frames["telemetry"].to_dicts() == [{"id": "A", "first": 1}]
    else:
        assert result.invocation_statuses[merge_second_id] == "succeeded"
        assert result.invocation_statuses[write_id] == "succeeded"
        assert result.failures == {}
        assert result.main_frames["telemetry"].to_dicts() == [{"id": "A", "first": 1, "second": 2}]


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
                        id_columns=[],
                        arguments=(
                            invocation.arguments | {"target_keys": []}
                            if invocation.function_kind == "merge"
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
    assert isinstance(result.main_frames["telemetry"], pl.LazyFrame)
    assert collected_heights == [1]
    assert result.preview_frames["telemetry"].height == 1


@pytest.mark.parametrize(
    ("invalid", "message"),
    [
        ("key", "missing dimension columns"),
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
    assert not result.main_frames


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
    frame = unchecked.main_frames["telemetry"]
    if lazy:
        frame.collect()

    checked = runtime.run(validate=True)
    message = {
        "duplicates": "duplicate dimension keys",
        "types": "expected string",
        "row_count": "must preserve existing column values and row order",
        "keys": "must preserve existing column values and row order",
    }[invalid]
    assert message in next(iter(checked.failures.values()))
    assert len(writes) == 1
    assert "skipped" in checked.invocation_statuses.values()


def test_removed_lazy_validation_config_is_rejected() -> None:
    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        uptimely_engine.EngineBackendConfig.model_validate({"validate_lazy_frames": False})


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
    read = next(item for item in engine.plan.invocations if item.function_kind == "read")
    merge = next(item for item in engine.plan.invocations if item.function_kind == "merge")
    calculate = next(item for item in engine.plan.invocations if item.function_kind == "vectorize")

    executor.execute(read)
    assert state.main_frames == {}
    assert set(state.staged_fragments) == {read.id}
    executor.execute(merge)
    main = state.main_frames["telemetry"]
    source = main.fragments[read.operator_id]
    assert main.id_columns == ("asset_id",)
    assert not hasattr(main, "dataset")
    assert source.dataframe.columns == ["asset_id", "reading"]

    executor.execute(calculate)

    assert state.main_frames["telemetry"] is main
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
    assert result.main_frames["telemetry"]["doubled"].to_list() == [4, 6]


def test_engine_reports_package_provenance_without_enforcing_versions(
    monkeypatch: pytest.MonkeyPatch, engine_for_plan: execution_support.EngineFactory
) -> None:
    engine = engine_for_plan(_plan())
    runtime_package = entrypoint_module.PackageProvenance("runtime-package", "2.0")
    monkeypatch.setattr(
        entrypoint_module.PackageProvenance,
        "read",
        lambda _module: runtime_package,
    )
    executor = execution_module.InvocationExecutor(
        engine.backend,
        {
            location: entrypoint_module.Entrypoint(
                location,
                package=entrypoint_module.PackageProvenance("recorded-package", "1.0"),
            )
            for location in ("uptimely.entrypoint:PackageProvenance", "math:pi")
        },
        engine.parameters,
        state_module.RuntimeState(),
    )

    invocation = copy.replace(
        engine.plan.invocations[0],
        entrypoint="uptimely.entrypoint:PackageProvenance",
        arguments={"distribution": "recorded-package", "version": "1.0"},
    )

    assert executor._invoke(invocation) == entrypoint_module.PackageProvenance(
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
        main_frames={
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
        function_kind="vectorize",
        entrypoint="test:calculate",
        function_id="calculate",
        operator_id="calculate",
        dataset_id="dataset",
        input_features=["local"],
    )

    executor.check_input_requirements(invocation)
    invocation.input_features[:] = ["unique"]
    executor.check_input_requirements(invocation)
    invocation.input_features[:] = ["shared"]
    with pytest.raises(ValueError, match="unavailable or ambiguous: shared"):
        executor.check_input_requirements(invocation)
    runtime_state.main_frames["dataset"].dataframe = pl.DataFrame({"new": [1]})
    del runtime_state.main_frames["second"]
    invocation.input_features[:] = ["new"]
    executor.check_input_requirements(invocation)
    invocation.input_features[:] = ["shared"]
    executor.check_input_requirements(invocation)
    assert (
        caplog.messages
        == [
            "  Requirements:",
            "    - checking declared input features",
        ]
        * 5
    )


def test_engine_entrypoints_include_saved_package_provenance(
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    saved_plan = _plan()
    location = saved_plan.invocations[0].entrypoint
    saved_plan.resources["entrypoint_packages"] = {
        location: {"distribution": "recorded-package", "version": "1.0"}
    }
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
    assert first_result.main_frames is not second_result.main_frames
    assert first_result.calculated_outputs is not second_result.calculated_outputs
    assert first_result.main_frames["telemetry"]["doubled"].to_list() == [2, 4]
    assert second_result.main_frames["telemetry"]["doubled"].to_list() == [4, 6]
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
    return_value: object,
    monkeypatch: pytest.MonkeyPatch,
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    invocation_id = "invocation:escape:external_operator:asset:external:operator"
    escape = uptimely_plan.Invocation(
        id=invocation_id,
        function_kind="escape",
        entrypoint="test:escape",
        function_id="external_operator",
        operator_id="operator",
        dataset_id="external",
        output_features=[],
        input_features=["external_input"],
    )
    plan = uptimely_plan.ExecutionPlan(
        plan_version=6,
        required_backend="polars",
        resources={
            "profiles": {"external": {"grain": []}},
            "functions": {
                "external_operator": {
                    "kind": "escape",
                    "returns": "any",
                    "args": {},
                }
            },
        },
        invocations=[escape],
        stages=[[invocation_id]],
    )
    _patch_callables(monkeypatch, {"test:escape": lambda: return_value})
    engine = engine_for_plan(plan)

    result = engine.run()

    assert result.invocation_statuses == {invocation_id: "succeeded"}
    assert result.failures == {}
    assert result.main_frames == {}
    assert result.calculated_outputs == {}


def test_escape_feature_outputs_order_invocations_without_materializing_dataframes(
    monkeypatch: pytest.MonkeyPatch, engine_for_plan: execution_support.EngineFactory
) -> None:
    first_id = "invocation:escape:first:asset:external:first"
    second_id = "invocation:escape:second:asset:external:second"
    calls: list[str] = []

    def first() -> int:
        calls.append("first")
        return 17

    def second() -> object:
        calls.append("second")
        return object()

    first_invocation = uptimely_plan.Invocation(
        id=first_id,
        function_kind="escape",
        entrypoint="test:first",
        function_id="first",
        operator_id="first",
        dataset_id="external",
        output_features=["first_output"],
        input_features=["external_input"],
    )
    second_invocation = uptimely_plan.Invocation(
        id=second_id,
        function_kind="escape",
        entrypoint="test:second",
        function_id="second",
        operator_id="second",
        dataset_id="external",
        output_features=[],
        input_features=["first_output"],
        dependency_ids=[first_id],
    )
    plan = uptimely_plan.ExecutionPlan(
        plan_version=6,
        required_backend="polars",
        resources={
            "profiles": {"external": {"grain": []}},
            "functions": {
                function_id: {"kind": "escape", "returns": "any", "args": {}}
                for function_id in ("first", "second")
            },
        },
        invocations=[first_invocation, second_invocation],
        stages=[[first_id], [second_id]],
    )

    _patch_callables(monkeypatch, {"test:first": first, "test:second": second})
    result = engine_for_plan(plan).run()

    assert calls == ["first", "second"]
    assert result.invocation_statuses == {first_id: "succeeded", second_id: "succeeded"}
    assert result.failures == {}
    assert result.main_frames == {}
    assert result.calculated_outputs == {}


def test_escape_resolves_literal_and_runtime_arguments(
    monkeypatch: pytest.MonkeyPatch, engine_for_plan: execution_support.EngineFactory
) -> None:
    invocation_id = "invocation:escape:external_operator:asset:external:operator"
    escape = uptimely_plan.Invocation(
        id=invocation_id,
        function_kind="escape",
        entrypoint="test:escape",
        function_id="external_operator",
        operator_id="operator",
        dataset_id="external",
        output_features=[],
        input_features=["external_input"],
        arguments={"path": "$params.output", "mode": "replace"},
    )
    plan = uptimely_plan.ExecutionPlan(
        plan_version=6,
        required_backend="polars",
        resources={
            "profiles": {"external": {"grain": []}},
            "functions": {
                "external_operator": {
                    "kind": "escape",
                    "returns": "any",
                    "args": {
                        "path": {"type": "string"},
                        "mode": {"type": "string"},
                    },
                }
            },
        },
        invocations=[escape],
        stages=[[invocation_id]],
    )
    received: list[tuple[str, str]] = []

    def external_operator(path: str, mode: str) -> None:
        received.append((path, mode))

    _patch_callables(monkeypatch, {"test:escape": external_operator})
    result = engine_for_plan(plan, {"output": "/tmp/external-output.csv"}).run()

    assert received == [("/tmp/external-output.csv", "replace")]
    assert result.invocation_statuses == {invocation_id: "succeeded"}
    assert result.failures == {}


def test_escape_missing_explicit_dataframe_argument_fails_and_skips_downstream(
    monkeypatch: pytest.MonkeyPatch, engine_for_plan: execution_support.EngineFactory
) -> None:
    first_id = "invocation:escape:first:asset:external:first"
    second_id = "invocation:escape:second:asset:external:second"
    first_invocation = uptimely_plan.Invocation(
        id=first_id,
        function_kind="escape",
        entrypoint="test:first",
        function_id="first",
        operator_id="first",
        dataset_id="external",
        output_features=[],
        input_features=["external_input"],
        arguments={"frame": "missing"},
    )
    second_invocation = copy.replace(
        first_invocation,
        id=second_id,
        entrypoint="test:second",
        function_id="second",
        operator_id="second",
        output_features=[],
        dependency_ids=[first_id],
    )
    plan = uptimely_plan.ExecutionPlan(
        plan_version=6,
        required_backend="polars",
        resources={
            "profiles": {"external": {"grain": []}},
            "functions": {
                function_id: {
                    "kind": "escape",
                    "returns": "any",
                    "args": {"frame": {"type": "dataframe"}},
                }
                for function_id in ("first", "second")
            },
        },
        invocations=[first_invocation, second_invocation],
        stages=[[first_id], [second_id]],
    )

    _patch_callables(monkeypatch, {"test:first": lambda **_: None, "test:second": lambda **_: None})
    result = engine_for_plan(plan).run()

    assert result.invocation_statuses == {first_id: "failed", second_id: "skipped"}
    assert "Profile dataframe is unavailable: missing" in result.failures[first_id]


def test_escape_outputs_are_not_passed_to_following_dataframe_invocations(
    monkeypatch: pytest.MonkeyPatch, engine_for_plan: execution_support.EngineFactory
) -> None:
    read_id = "invocation:read:load:asset:telemetry:load"
    merge_id = "invocation:merge:combine:asset:telemetry:load"
    escape_id = "invocation:escape:external_operator:asset:telemetry:operator"
    vectorize_id = "invocation:vectorize:consume:asset:telemetry:consume"
    observed: list[pl.DataFrame] = []

    def read() -> pl.DataFrame:
        return pl.DataFrame({"asset_id": ["A"], "reading": [3]})

    def external_operator(dataset: pl.DataFrame) -> pl.DataFrame:
        observed.append(dataset)
        return pl.DataFrame({"external_result": [4]})

    def consume() -> pl.DataFrame:
        pytest.fail("The dataframe operator must not run without its declared input feature")

    read_invocation = uptimely_plan.Invocation(
        id=read_id,
        function_kind="read",
        entrypoint="test:read",
        function_id="load",
        operator_id="load",
        dataset_id="telemetry",
        output_features=["asset_id", "reading"],
    )
    merge_invocation = uptimely_plan.Invocation(
        id=merge_id,
        function_kind="merge",
        entrypoint="test:merge",
        function_id="combine",
        operator_id="load",
        dataset_id="telemetry",
        id_columns=["asset_id"],
        arguments={
            "target": "telemetry",
            "fragment": "$operators.@.fragment",
            "target_keys": ["asset_id"],
        },
        argument_types={
            "target": "dataframe | null",
            "fragment": "dataframe",
            "target_keys": "array[string]",
        },
        dependency_ids=[read_id],
    )
    escape_invocation = uptimely_plan.Invocation(
        id=escape_id,
        function_kind="escape",
        entrypoint="test:escape",
        function_id="external_operator",
        operator_id="external_result",
        dataset_id="telemetry",
        output_features=["external_result"],
        input_features=["reading"],
        arguments={"dataset": "telemetry"},
        dependency_ids=[merge_id],
    )
    vectorize_invocation = uptimely_plan.Invocation(
        id=vectorize_id,
        function_kind="vectorize",
        entrypoint="test:consume",
        function_id="consume",
        operator_id="consume",
        dataset_id="telemetry",
        output_features=["processed"],
        input_features=["external_result"],
        dependency_ids=[escape_id],
    )
    plan = uptimely_plan.ExecutionPlan(
        plan_version=6,
        required_backend="polars",
        resources={
            "dimensions": {
                "asset_id": {"resolutions": {"asset_id": {"key": "asset_id", "type": "string"}}}
            },
            "profiles": {
                "telemetry": {"grain": [{"dimension": "asset_id", "resolution": "asset_id"}]}
            },
            "functions": {
                "load": {"kind": "read", "returns": "dataframe", "args": {}},
                "combine": {"kind": "merge", "returns": "dataframe", "args": {}},
                "external_operator": {
                    "kind": "escape",
                    "returns": "any",
                    "args": {"dataset": {"type": "dataframe"}},
                },
                "consume": {"kind": "vectorize", "returns": "dataframe", "args": {}},
            },
        },
        invocations=[read_invocation, merge_invocation, escape_invocation, vectorize_invocation],
        stages=[[read_id], [merge_id], [escape_id], [vectorize_id]],
    )

    _patch_callables(
        monkeypatch,
        {
            "test:read": read,
            "test:escape": external_operator,
            "test:consume": consume,
            "test:merge": merge_module.merge_by_grain,
        },
    )
    result = engine_for_plan(plan).run(validate=True)

    assert result.invocation_statuses == {
        read_id: "succeeded",
        merge_id: "succeeded",
        escape_id: "succeeded",
        vectorize_id: "failed",
    }
    assert (
        "input feature is unavailable or ambiguous: external_result"
        in result.failures[vectorize_id]
    )
    assert observed == [result.main_frames["telemetry"]]
    assert "external_result" not in result.main_frames["telemetry"].columns
    assert result.calculated_outputs == {}


def test_escape_exception_fails_and_skips_downstream(
    monkeypatch: pytest.MonkeyPatch, engine_for_plan: execution_support.EngineFactory
) -> None:
    first_id = "invocation:escape:first:asset:external:first"
    second_id = "invocation:escape:second:asset:external:second"
    first_invocation = uptimely_plan.Invocation(
        id=first_id,
        function_kind="escape",
        entrypoint="test:first",
        function_id="first",
        operator_id="first",
        dataset_id="external",
        output_features=[],
        input_features=["external_input"],
    )
    second_invocation = copy.replace(
        first_invocation,
        id=second_id,
        entrypoint="test:second",
        function_id="second",
        operator_id="second",
        output_features=[],
        dependency_ids=[first_id],
    )
    plan = uptimely_plan.ExecutionPlan(
        plan_version=6,
        required_backend="polars",
        resources={
            "profiles": {"external": {"grain": []}},
            "functions": {
                function_id: {"kind": "escape", "returns": "any", "args": {}}
                for function_id in ("first", "second")
            },
        },
        invocations=[first_invocation, second_invocation],
        stages=[[first_id], [second_id]],
    )

    def fail() -> None:
        raise RuntimeError("external operator failed")

    _patch_callables(monkeypatch, {"test:first": fail, "test:second": lambda: None})
    result = engine_for_plan(plan).run()

    assert result.invocation_statuses == {first_id: "failed", second_id: "skipped"}
    assert result.failures == {first_id: "external operator failed"}


def test_python_spec_escape_executes_after_json_plan_reload_with_local_storage(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    source_path = tmp_path / "input.csv"
    output_path = tmp_path / "output.csv"
    plan_path = tmp_path / "execution_plan.json"
    source_path.write_text("asset_id,value\nA,2\nB,3\n", encoding="utf-8")
    package_name = f"engine_fixture_{tmp_path.name.replace('-', '_')}"
    package = tmp_path / package_name
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "external_operator.py").write_text(
        "import polars as pl\n"
        f"SOURCE = {str(source_path)!r}\n"
        f"OUTPUT = {str(output_path)!r}\n"
        "def process() -> None:\n"
        "    frame = pl.read_csv(SOURCE)\n"
        "    result = frame.with_columns((pl.col('value') * 2).alias('external_result'))\n"
        "    result.write_csv(OUTPUT)\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    declaration = profile.Profile(
        id="external",
        grain=[
            profile.Grain(
                dimension.Dimension(
                    id="asset",
                    resolutions=[dimension.Resolution(id="asset", key="asset_id", type="string")],
                ),
                "asset",
            )
        ],
        assembly=[
            assembly.Operator(
                id="external_operator",
                interface=assembly.Interface(
                    inputs=[ref.feature("asset_id")],
                    outputs=[],
                ),
                compute=assembly.Binding(
                    function=ref.function(
                        f"{package_name}.external_operator:process", kind="escape"
                    ),
                    arguments={},
                ),
            )
        ],
    )
    spec_definition = spec.from_python(profiles=[declaration])

    compiled = uptimely_compiler.Compiler().compile(spec_definition)
    plan_serialization.export_json(compiled, plan_path)
    restored = uptimely_plan.from_json(plan_path)
    result = engine_for_plan(restored, project_root=tmp_path).run()

    assert result.failures == {}
    assert result.invocation_statuses == {compiled.invocations[0].id: "succeeded"}
    assert result.main_frames == {}
    assert result.calculated_outputs == {}
    assert pl.read_csv(output_path).rows() == [("A", 2, 4), ("B", 3, 6)]


def test_engine_validates_plan_backend(engine_for_plan: execution_support.EngineFactory) -> None:
    plan = _plan()

    with pytest.raises(ValueError, match="Unsupported plan backend"):
        engine_for_plan(copy.replace(plan, required_backend="pandas"))


@pytest.mark.parametrize("validate", [False, True])
def test_engine_execution_uses_only_saved_invocation_metadata(
    monkeypatch: pytest.MonkeyPatch,
    bundle_for_plan: execution_support.BundleFactory,
    validate: bool,
) -> None:
    raw = pl.DataFrame({"asset_id": ["A"], "reading": [2], "extra": [0]})

    def double(column: str, dataset: pl.DataFrame) -> pl.DataFrame:
        assert dataset.columns == ["asset_id", "reading"]
        return dataset.with_columns((pl.col(column) * 2).alias("doubled"))

    _patch_callables(
        monkeypatch,
        {
            "test:read": lambda **_: raw,
            "test:double": double,
            "test:write": lambda **_: None,
        },
    )
    bundle = bundle_for_plan(_plan())
    restored = uptimely_plan.from_dict(uptimely_plan.to_dict(bundle.execution_plan))
    bundle = copy.replace(bundle, execution_plan=restored, spec_definition=spec.Spec())
    engine = uptimely_engine.Engine(
        bundle, uptimely_engine.EngineConfig(), {"source": "input.json"}
    )

    result = engine.run(validate=validate)

    assert not result.failures
    assert result.main_frames["telemetry"].to_dicts() == [
        {"asset_id": "A", "reading": 2, "doubled": 4}
    ]


def test_engine_selects_dataframe_backend_from_config(
    bundle_for_plan: execution_support.BundleFactory,
) -> None:
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


@pytest.mark.parametrize("reference", ["$params.", "$params.source.path"])
def test_engine_rejects_malformed_parameter_references(
    reference: str, engine_for_plan: execution_support.EngineFactory
) -> None:
    engine = engine_for_plan(_plan())
    bindings = bindings_module.RuntimeBindings(state_module.RuntimeState(), engine.parameters)

    with pytest.raises(ValueError, match="Malformed parameter reference"):
        bindings.resolve_parameter_reference(reference)


def test_engine_rejects_ambiguous_fragment_references() -> None:
    first = execution_support.dataset(None)
    second = execution_support.dataset(None)
    first.fragments["shared"] = fragment_module.Fragment(pl.DataFrame({"asset_id": ["A"]}), ())
    second.fragments["shared"] = fragment_module.Fragment(pl.DataFrame({"asset_id": ["B"]}), ())
    state = state_module.RuntimeState(main_frames={"first": first, "second": second})

    with pytest.raises(ValueError, match="Ambiguous fragment reference: shared"):
        state.resolve_dataset_or_fragment_dataframe("shared")


def test_fragment_names_are_scoped_by_dataset_not_entity(
    monkeypatch: pytest.MonkeyPatch, engine_for_plan: execution_support.EngineFactory
) -> None:
    def read(source: str) -> pl.DataFrame:
        return pl.DataFrame({"asset_id": [source], "reading": [1]})

    _patch_callables(monkeypatch, {"test:read": read})
    engine = engine_for_plan(_plan(), {"source": "source"})
    state = state_module.RuntimeState()
    executor = execution_module.InvocationExecutor(
        engine.backend,
        {},
        engine.parameters,
        state,
    )
    for dataset_id in ("first", "second"):
        read = copy.replace(
            next(item for item in engine.plan.invocations if item.function_kind == "read"),
            dataset_id=dataset_id,
            operator_id="shared",
        )
        merge = copy.replace(
            next(item for item in engine.plan.invocations if item.function_kind == "merge"),
            id=f"invocation:merge:__uptimely_merge_by_grain:{dataset_id}:shared",
            dataset_id=dataset_id,
            operator_id="shared",
            arguments={
                "target": dataset_id,
                **{
                    key: value
                    for key, value in next(
                        item for item in engine.plan.invocations if item.function_kind == "merge"
                    ).arguments.items()
                    if key != "target"
                },
            },
            dependency_ids=[read.id],
        )
        executor.execute(read)
        executor.execute(merge)

    assert set(state.main_frames) == {"first", "second"}
    assert all(set(main.fragments) == {"shared"} for main in state.main_frames.values())
    with pytest.raises(ValueError, match="Ambiguous fragment reference: shared"):
        state.resolve_dataset_or_fragment_dataframe("shared")


def test_input_validation_reads_each_dataset_schema_once(
    monkeypatch: pytest.MonkeyPatch, engine_for_plan: execution_support.EngineFactory
) -> None:
    engine = engine_for_plan(_plan())
    state = state_module.RuntimeState(
        main_frames={
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
    assert inspected[0] is state.main_frames["telemetry"].dataframe
    assert inspected[1] is state.main_frames["source"].dataframe


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
        function_kind="expand",
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
        invocation.arguments["source"] = invocation.dataset_id
    elif invalid == "missing_source":
        invocation.arguments["source"] = "missing"
    elif invalid == "missing_feature":
        invocation.input_features[:] = ["missing"]
    state = state_module.RuntimeState(
        main_frames={"source": execution_support.dataset(pl.DataFrame({"reading": [1]}))}
    )
    executor = execution_module.InvocationExecutor(
        backend_module.PolarsBackend(), {}, {}, state, validate=True
    )

    if message is None:
        executor.check_input_requirements(invocation)
    else:
        with pytest.raises(ValueError, match=message):
            executor.check_input_requirements(invocation)

    assert caplog.messages == [
        "  Requirements:",
        *[
            "    - checking foreign dataframe argument",
            "    - checking foreign source reference",
            "    - checking foreign source availability",
            "    - checking foreign input features",
        ][:check_count],
    ]


@pytest.mark.parametrize("sources", [0, 2])
def test_input_validation_rejects_missing_or_ambiguous_foreign_features(
    sources: int, engine_for_plan: execution_support.EngineFactory
) -> None:
    engine = engine_for_plan(_plan())
    state = state_module.RuntimeState(
        main_frames={
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
    state = state_module.RuntimeState(main_frames={"shared": main})

    assert state.resolve_dataset_or_fragment_dataframe("shared") is dataset


def test_runtime_state_is_not_shared_between_instances() -> None:
    first = state_module.RuntimeState()
    second = state_module.RuntimeState()
    first.main_frames["telemetry"] = execution_support.dataset(pl.DataFrame({"asset_id": ["A"]}))

    assert second.main_frames == {}


def test_vectorize_requires_an_accumulated_target() -> None:
    executor = execution_module.InvocationExecutor(
        backend_module.PolarsBackend(),
        {},
        {},
        state_module.RuntimeState(),
    )
    invocation = uptimely_plan.Invocation(
        id="vectorize",
        function_kind="vectorize",
        entrypoint="test:calculate",
        function_id="calculate",
        operator_id="calculate",
        dataset_id="telemetry",
    )

    with pytest.raises(ValueError, match="Profile dataframe is unavailable: telemetry"):
        executor.execute(invocation)


def test_column_projection_failure_preserves_published_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = pl.DataFrame({"reading": [3]})
    dataset = execution_support.dataset(original)
    state = state_module.RuntimeState(main_frames={"telemetry": dataset})
    adapter = backend_module.PolarsBackend()
    executor = execution_module.InvocationExecutor(adapter, {}, {}, state)
    invocation = uptimely_plan.Invocation(
        id="vectorize",
        function_kind="vectorize",
        entrypoint="test:calculate",
        function_id="calculate",
        operator_id="calculate",
        dataset_id="telemetry",
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
    state = state_module.RuntimeState(main_frames={"dataset": dataset})
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
        function_kind="vectorize",
        entrypoint="test:calculate",
        function_id="calculate",
        operator_id="calculate",
        dataset_id="dataset",
        id_columns=["key"],
        output_features=["doubled"],
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

    staged_kinds: list[str] = []
    stage_fragment = fragment_module.Fragment.stage
    merge_calls = 0
    merge_by_grain = merge_module.merge_by_grain

    def stage_spy(backend: object, invocation: object, load: object, **kwargs: object) -> object:
        staged_kinds.append(invocation.function_kind)
        return stage_fragment(backend, invocation, load, **kwargs)

    def merge_spy(*args: object, **kwargs: object) -> object:
        nonlocal merge_calls
        merge_calls += 1
        return merge_by_grain(*args, **kwargs)

    read_invocation = uptimely_plan.Invocation(
        id="invocation:read:load:asset:telemetry:load",
        function_kind="read",
        entrypoint="test:read",
        function_id="load",
        operator_id="load",
        dataset_id="telemetry",
        output_features=["asset_id", "reading"],
    )
    merge_invocation = uptimely_plan.Invocation(
        id="invocation:merge:merge_by_grain:asset:telemetry:load",
        function_kind="merge",
        entrypoint="uptimely.library.merge.polars:merge_by_grain",
        function_id="merge_by_grain",
        operator_id="load",
        dataset_id="telemetry",
        output_features=[],
        input_features=[],
        arguments={
            "target": "telemetry",
            "fragment": "$operators.@.fragment",
            "target_keys": ["asset_id"],
        },
        dependency_ids=[read_invocation.id],
        id_columns=["asset_id"],
        column_types={},
        argument_types={
            "target": "dataframe | null",
            "fragment": "dataframe",
            "target_keys": "array[string]",
        },
    )
    vectorize_invocation = uptimely_plan.Invocation(
        id="invocation:vectorize:calculate:asset:telemetry:reading_plus_one",
        function_kind="vectorize",
        entrypoint="test:calculate",
        function_id="calculate",
        operator_id="reading_plus_one",
        dataset_id="telemetry",
        output_features=["reading_plus_one", "reading_times_two"],
        arguments={"dataset": "telemetry"},
        argument_types={"dataset": "dataframe"},
        dependency_ids=[merge_invocation.id],
    )
    plan = uptimely_plan.ExecutionPlan(
        plan_version=6,
        required_backend="polars",
        resources={
            "dimensions": {
                "asset_id": {"resolutions": {"asset_id": {"key": "asset_id", "type": "string"}}}
            },
            "profiles": {
                "telemetry": {"grain": [{"dimension": "asset_id", "resolution": "asset_id"}]}
            },
            "functions": {
                "load": {"kind": "read", "args": {}},
                "merge_by_grain": {"kind": "merge", "args": {}},
                "calculate": {"kind": "vectorize", "args": {}},
            },
        },
        invocations=[read_invocation, merge_invocation, vectorize_invocation],
        stages=[[read_invocation.id], [merge_invocation.id], [vectorize_invocation.id]],
    )
    _patch_callables(monkeypatch, {"test:read": read, "test:calculate": calculate})
    monkeypatch.setattr(fragment_module.Fragment, "stage", staticmethod(stage_spy))
    monkeypatch.setattr(merge_module, "merge_by_grain", merge_spy)
    engine = engine_for_plan(plan)

    result = engine.run()

    assert result.failures == {}
    assert calls == 1
    assert result.main_frames["telemetry"]["reading"].to_list() == [3]
    assert result.main_frames["telemetry"].select(
        "reading_plus_one", "reading_times_two"
    ).rows() == [(4, 6)]
    assert staged_kinds == ["read"]
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
