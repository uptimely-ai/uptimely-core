import collections.abc
import logging
import pathlib
import types

import polars as pl
import pytest
from support import execution as execution_support

from uptimely import plan as uptimely_plan
from uptimely.codebase.python import entrypoint as entrypoint_module
from uptimely.library.merge import polars as merge_module
from uptimely.run import store as run_store

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


@pytest.mark.parametrize("operator_id", ["reading", "doubled"])
def test_targeted_run_excludes_downstream_work_and_records_saved_identity(
    monkeypatch: pytest.MonkeyPatch,
    engine_for_plan: execution_support.EngineFactory,
    operator_id: str,
) -> None:
    calls: list[str] = []

    def read(source: str) -> pl.DataFrame:
        calls.append("read")
        return pl.DataFrame({"asset_id": ["A", "B"], "reading": [2, 3]})

    def double(column: str, dataset: pl.DataFrame) -> pl.DataFrame:
        calls.append("double")
        return dataset.with_columns((pl.col(column) * 2).alias("doubled"))

    def write(dataset: pl.DataFrame, features: list[str]) -> None:
        pytest.fail("A targeted analytical request must not execute a downstream sink")

    _patch_callables(monkeypatch, {"test:read": read, "test:double": double, "test:write": write})
    runtime = engine_for_plan(_plan(), {"source": "/tmp/telemetry.parquet"})
    original_plan = runtime.plan

    result = runtime.run(operator=("telemetry", operator_id), preview_rows=1)

    assert result.failures == {}
    assert calls == (["read"] if operator_id == "reading" else ["read", "double"])
    preview = result.preview_frames["telemetry"]
    assert isinstance(preview, pl.DataFrame)
    assert preview.height == 1
    assert runtime.plan is original_plan
    assert runtime.bundle.execution_plan is original_plan
    selected = original_plan.for_operator("telemetry", operator_id)
    for invocation in original_plan.invocations:
        assert result.invocation_statuses[invocation.id] == (
            "succeeded" if invocation.id in selected.invocations_by_id else "skipped"
        )
    manifest = run_store.RunStore(runtime.bundle.project_root).read_manifest()
    assert manifest.status == "succeeded"
    assert {
        invocation_id: outcome.status for invocation_id, outcome in manifest.invocations.items()
    } == result.invocation_statuses


def test_targeted_run_rejects_missing_operator_without_replacing_last_run(
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    runtime = engine_for_plan(_plan())
    with pytest.raises(ValueError, match="not in the saved execution scope"):
        runtime.run(operator=("unknown", "unknown"))
    with pytest.raises(run_store.RunNotFoundError):
        run_store.RunStore(runtime.bundle.project_root).read_manifest()


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
    assert result.plan_version == uptimely_plan.PLAN_VERSION

    assert isinstance(result.calculated_outputs["telemetry", "doubled"], pl.DataFrame)
    assert set(result.datasets) == {"telemetry"}
    assert result.datasets["telemetry"].select("doubled").to_series().to_list() == [
        4,
        6,
    ]
    assert written["features"] == ["doubled"]
    assert written["dataset"].select("asset_id", "doubled").rows() == [("A", 4), ("B", 6)]
    executions = [
        message for message in caplog.messages if message.startswith("Executing operator ")
    ]
    assert executions == [
        f"Executing operator {invocation.operator_id}, "
        f"function {invocation.function_id} (role={invocation.role}, result={invocation.result})"
        for invocation in engine.plan.execution_invocations
    ]
    assert caplog.messages.count("Merging into profile telemetry") == 1
    assert any(
        message.startswith("Check fragment dataframe type from operator ")
        and "profile telemetry" in message
        for message in caplog.messages
    )
    assert all("\n" not in message and message == message.lstrip() for message in caplog.messages)
    execution_records = [
        record for record in caplog.records if record.getMessage().startswith("Executing operator ")
    ]
    assert execution_records
    assert all(
        record.invocation_id and record.profile_id == "telemetry" for record in execution_records
    )


@pytest.mark.parametrize("merge_failure", [None, "exception", "incomplete"])
def test_custom_merges_receive_computed_fragment_and_publish_only_on_success(
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
        dataset: pl.DataFrame | None,
        fragment: pl.DataFrame,
        dataset_identifiers: list[str],
    ) -> pl.DataFrame:
        merge_inputs.append((dataset.columns if dataset is not None else None, fragment.columns))
        if dataset is not None and merge_failure == "exception":
            raise RuntimeError("custom merge failed")
        if dataset is not None and merge_failure == "incomplete":
            return fragment
        return merge_module.merge_by_grain(dataset, fragment, dataset_identifiers)

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
            role="compute",
            result="fragment",
            fragment_dimensions="target",
            entrypoint="test:read_first",
            function_id="read_first",
            operator_id="first",
            profile_id="telemetry",
            output_features=["id", "first"],
            target_identifiers=["id"],
        ),
        uptimely_plan.Invocation(
            id=read_second_id,
            role="compute",
            result="fragment",
            fragment_dimensions="target",
            entrypoint="test:read_second",
            function_id="read_second",
            operator_id="second",
            profile_id="telemetry",
            output_features=["id", "second"],
            target_identifiers=["id"],
        ),
    ]

    def merge_invocation(
        invocation_id: str, operator_id: str, compute_id: str, dependencies: list[str]
    ) -> uptimely_plan.Invocation:
        return uptimely_plan.Invocation(
            id=invocation_id,
            role="merge",
            result="target",
            entrypoint="test:custom_merge",
            function_id="custom_merge",
            operator_id=operator_id,
            profile_id="telemetry",
            arguments={
                "dataset": "telemetry",
                "fragment": "$operators.@.fragment",
                "dataset_identifiers": ["id"],
            },
            dependency_ids=[compute_id, *dependencies],
            target_identifiers=["id"],
            argument_types={
                "dataset": "dataframe | null",
                "fragment": "dataframe",
                "dataset_identifiers": "array[string]",
            },
        )

    first_merge = merge_invocation(merge_first_id, "first", read_first_id, [])
    second_merge = merge_invocation(merge_second_id, "second", read_second_id, [merge_first_id])
    writer = uptimely_plan.Invocation(
        id=write_id,
        role="compute",
        result="none",
        entrypoint="test:write",
        function_id="write",
        operator_id="write",
        profile_id="telemetry",
        arguments={"dataset": "telemetry"},
        dependency_ids=[merge_second_id],
        argument_types={"dataset": "dataframe"},
    )
    plan = uptimely_plan.ExecutionPlan(
        plan_version=uptimely_plan.PLAN_VERSION,
        required_backend="polars",
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
        assert result.datasets["telemetry"].to_dicts() == [{"id": "A", "first": 1}]
    else:
        assert result.invocation_statuses[merge_second_id] == "succeeded"
        assert result.invocation_statuses[write_id] == "succeeded"
        assert result.failures == {}
        assert result.datasets["telemetry"].to_dicts() == [{"id": "A", "first": 1, "second": 2}]
