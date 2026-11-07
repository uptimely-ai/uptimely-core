"""Persistence contracts for complete, failed, and replaced engine runs."""

import concurrent.futures
import copy
import datetime
import decimal
import json
import logging
import os
import pathlib

import polars as pl
import pytest
from support import execution as execution_support

from uptimely import engine, project_paths
from uptimely import plan as execution_plan
from uptimely.run import models, store

PLAN_PATH = pathlib.Path(__file__).parents[2] / "fixtures/plans/simple_engine.json"


@pytest.fixture
def runtime(bundle_for_plan: execution_support.BundleFactory) -> engine.Engine:
    bundle = bundle_for_plan(execution_plan.from_json(PLAN_PATH))
    return engine.Engine(bundle, engine.EngineConfig(), {"secret": "not-in-manifest"})


def _result(frame: object | None = None) -> engine.ExecutionResult:
    return engine.ExecutionResult(
        main_frames={} if frame is None else {"telemetry": frame},
        calculated_outputs={},
        invocation_statuses={},
        durations={},
        failures={},
        plan_version=6,
    )


@pytest.mark.parametrize("lazy", [False, True])
@pytest.mark.parametrize("row_count", [0, 3, 10])
def test_run_persists_bounded_schema_and_reuses_preview(
    runtime: engine.Engine, monkeypatch: pytest.MonkeyPatch, lazy: bool, row_count: int
) -> None:
    frame = pl.DataFrame({"value": range(row_count)}, schema={"value": pl.Int64})
    output = frame.lazy() if lazy else frame
    monkeypatch.setattr(runtime, "_execute", lambda **kwargs: _result(output))
    collected: list[int] = []
    original_collect = pl.LazyFrame.collect

    def collect(frame: pl.LazyFrame, *args: object, **kwargs: object) -> pl.DataFrame:
        sample = original_collect(frame, *args, **kwargs)
        collected.append(sample.height)
        return sample

    monkeypatch.setattr(pl.LazyFrame, "collect", collect)
    result = runtime.run(validate=True, preview_rows=2)
    saved = store.RunStore(runtime.bundle.project_root)
    manifest = saved.read_manifest()
    sample = saved.read_preview("telemetry", run_id=manifest.run_id)

    assert manifest.status == "succeeded"
    assert manifest.runtime_validation
    assert manifest.duration_seconds == result.duration_seconds
    assert manifest.finished_at >= manifest.started_at
    assert manifest.profiles["telemetry"].row_count == (None if lazy else row_count)
    assert manifest.profiles["telemetry"].column_count == 1
    assert sample.columns == [models.PreviewColumn(name="value", dtype="Int64")]
    assert sample.rows == [[value] for value in range(min(row_count, 2))]
    collected_frame = result.preview_frames["telemetry"]
    assert isinstance(collected_frame, pl.DataFrame)
    assert collected_frame.equals(frame.head(2))
    assert collected == ([min(row_count, 2)] if lazy else [])
    assert result.main_frames["telemetry"] is output
    assert "secret" not in manifest.model_dump_json()
    assert "format_version" not in manifest.model_dump()
    assert "run_version" not in manifest.model_dump()


def test_latest_run_completely_replaces_previous_profiles(
    runtime: engine.Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runtime, "_execute", lambda **kwargs: _result(pl.DataFrame({"a": [1]})))
    runtime.run()
    saved = store.RunStore(runtime.bundle.project_root)
    previous_id = saved.read_manifest().run_id
    monkeypatch.setattr(runtime, "_execute", lambda **kwargs: _result())
    runtime.run()

    manifest = saved.read_manifest()
    assert manifest.run_id != previous_id
    assert manifest.profiles == {}
    assert not (saved.root / saved.preview_path("telemetry")).exists()
    assert sorted(path.name for path in saved.root.iterdir()) == ["log.jsonl", "run.json"]
    assert not list(saved.root.parent.glob(".run-staging-*"))
    assert not list(saved.root.parent.glob(".run-backup-*"))
    with pytest.raises(store.RunChangedError):
        saved.read_logs(run_id=previous_id)
    with pytest.raises(store.RunChangedError):
        saved.read_preview("telemetry", run_id=previous_id)


def test_invocation_failure_persists_partial_results(
    runtime: engine.Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    read_id = next(item.id for item in runtime.plan.invocations if item.function_kind == "read")
    merge_id = next(item.id for item in runtime.plan.invocations if item.function_kind == "merge")
    failed_id = next(
        item.id for item in runtime.plan.invocations if item.function_kind == "vectorize"
    )
    skipped_id = next(item.id for item in runtime.plan.invocations if item.function_kind == "write")
    result = copy.replace(
        _result(pl.DataFrame({"reading": [1]})),
        invocation_statuses={
            read_id: "succeeded",
            merge_id: "succeeded",
            failed_id: "failed",
            skipped_id: "skipped",
        },
        durations={read_id: 0.1, merge_id: 0.1, failed_id: 0.2},
        failures={failed_id: "calculation failed"},
    )
    monkeypatch.setattr(runtime, "_execute", lambda **kwargs: result)

    returned = runtime.run()
    saved = store.RunStore(runtime.bundle.project_root)
    manifest = saved.read_manifest()

    assert manifest.status == "failed"
    assert manifest.invocations[failed_id].error == "calculation failed"
    assert manifest.invocations[failed_id].duration_seconds == 0.2
    assert manifest.invocations[skipped_id].duration_seconds is None
    assert saved.read_preview("telemetry").rows == [[1]]
    assert returned.failures == result.failures


@pytest.mark.parametrize("error", [RuntimeError("aborted"), KeyboardInterrupt()])
def test_unexpected_error_is_recorded_and_propagated_without_leaking_handlers(
    runtime: engine.Engine, monkeypatch: pytest.MonkeyPatch, error: BaseException
) -> None:
    def execute(**kwargs: object) -> engine.ExecutionResult:
        raise error

    monkeypatch.setattr(runtime, "_execute", execute)
    handlers = list(logging.getLogger().handlers)
    with pytest.raises(type(error)):
        runtime.run()

    saved = store.RunStore(runtime.bundle.project_root)
    manifest = saved.read_manifest()
    assert manifest.status == ("interrupted" if isinstance(error, KeyboardInterrupt) else "failed")
    assert manifest.error is not None
    assert type(error).__name__ in manifest.error
    assert saved.read_logs()[-1].exception
    assert logging.getLogger().handlers == handlers
    assert not list(saved.root.parent.glob(".run-staging-*"))


def test_preview_failure_is_explicit_and_does_not_change_execution_status(
    runtime: engine.Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad_frame = pl.LazyFrame({"a": [1]}).select("missing")
    monkeypatch.setattr(runtime, "_execute", lambda **kwargs: _result(bad_frame))
    result = runtime.run()
    saved = store.RunStore(runtime.bundle.project_root)
    manifest = saved.read_manifest()

    assert manifest.status == "succeeded"
    assert result.failures == {}
    assert "missing" in result.preview_failures["telemetry"]
    assert result.preview_frames == {}
    assert saved.read_preview("telemetry").status == "failed"
    assert saved.read_preview("telemetry").rows == []
    assert manifest.profiles["telemetry"].preview_error
    assert any(entry.profile_id == "telemetry" and entry.exception for entry in saved.read_logs())


def test_preview_values_are_lossless_and_browser_safe(
    runtime: engine.Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    frame = pl.DataFrame(
        {
            "integer": [2**63 - 1],
            "float": [float("inf")],
            "nan": [float("nan")],
            "decimal": [decimal.Decimal("123.450")],
            "date": [datetime.date(2026, 11, 3)],
            "datetime": [datetime.datetime(2026, 11, 3, 15, 0, tzinfo=datetime.UTC)],
            "duration": [datetime.timedelta(seconds=3)],
            "binary": [b"\x00\xff"],
            "list": [[1, None]],
            "struct": [{"x": decimal.Decimal("1.2")}],
        }
    )
    monkeypatch.setattr(runtime, "_execute", lambda **kwargs: _result(frame))
    runtime.run()
    sample = store.RunStore(runtime.bundle.project_root).read_preview("telemetry")

    assert sample.rows == [
        [
            str(2**63 - 1),
            "Infinity",
            "NaN",
            "123.450",
            "2026-11-03",
            "2026-11-03T15:00:00+00:00",
            "0:00:03",
            "AP8=",
            [1, None],
            {"x": "1.2"},
        ]
    ]


def test_json_logs_are_scoped_paginated_and_capture_multiline_messages(
    runtime: engine.Engine, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    logger = logging.getLogger("test.run")

    def execute(**kwargs: object) -> engine.ExecutionResult:
        logger.info("first\nsecond", extra={"invocation_id": "step"})
        with concurrent.futures.ThreadPoolExecutor() as pool:
            pool.submit(logger.warning, "unrelated thread").result()
        logger.warning("last")
        return _result()

    monkeypatch.setattr(runtime, "_execute", execute)
    before = list(logging.getLogger().handlers)
    runtime.run()
    saved = store.RunStore(runtime.bundle.project_root)
    entries = saved.read_logs()

    assert [entry.message for entry in entries] == ["first\nsecond", "last"]
    assert entries[0].invocation_id == "step"
    assert saved.read_logs(offset=1, limit=1) == [entries[1]]
    assert logging.getLogger().handlers == before
    assert len((saved.root / "log.jsonl").read_text().splitlines()) == 2


def test_promotion_failure_restores_old_run_and_cleans_staging(
    runtime: engine.Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runtime, "_execute", lambda **kwargs: _result())
    runtime.run()
    saved = store.RunStore(runtime.bundle.project_root)
    previous_id = saved.read_manifest().run_id
    original_replace = os.replace

    def replace(source: pathlib.Path, target: pathlib.Path) -> None:
        if source.name.startswith(".run-staging-"):
            raise OSError("promotion failed")
        original_replace(source, target)

    monkeypatch.setattr(store.os, "replace", replace)
    handlers = list(logging.getLogger().handlers)
    with pytest.raises(OSError, match="promotion failed"):
        runtime.run()

    assert saved.read_manifest().run_id == previous_id
    assert logging.getLogger().handlers == handlers
    assert not list(saved.root.parent.glob(".run-staging-*"))
    assert not list(saved.root.parent.glob(".run-backup-*"))


def test_run_storage_does_not_create_lock_files(
    runtime: engine.Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runtime, "_execute", lambda **kwargs: _result())
    runtime.run()
    saved = store.RunStore(runtime.bundle.project_root)
    saved.read_manifest()
    saved.read_logs()
    assert not list(saved.root.parent.glob("*.lock"))
    assert not list(saved.root.parent.glob(".*.lock"))


@pytest.mark.parametrize("rows", [0, -1, True, 1.5])
def test_invalid_preview_limit_does_not_execute_or_publish(
    runtime: engine.Engine, monkeypatch: pytest.MonkeyPatch, rows: int
) -> None:
    monkeypatch.setattr(runtime, "_execute", lambda **kwargs: pytest.fail("Must not execute"))
    with pytest.raises(ValueError, match="positive integer"):
        runtime.run(preview_rows=rows)
    assert not (runtime.bundle.project_root / project_paths.RUN_OUTPUT_DIR).exists()


def test_build_fingerprint_uses_loaded_objects_not_current_files(runtime: engine.Engine) -> None:
    identity = models.BuildIdentity.from_bundle(runtime.bundle)
    runtime.bundle.spec_path.write_text("changed after loading", encoding="utf-8")
    assert models.BuildIdentity.from_bundle(runtime.bundle) == identity
    other = copy.replace(
        runtime.bundle,
        execution_plan=copy.replace(runtime.plan, invocations=[], stages=[]),
    )
    assert models.BuildIdentity.from_bundle(other).fingerprint != identity.fingerprint


def test_preview_paths_and_symlinks_cannot_escape_snapshot(
    runtime: engine.Engine, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    unsafe_id = "../outside"
    result = copy.replace(_result(), main_frames={unsafe_id: pl.DataFrame({"x": [1]})})
    monkeypatch.setattr(runtime, "_execute", lambda **kwargs: result)
    runtime.run()
    saved = store.RunStore(runtime.bundle.project_root)
    assert saved.read_preview(unsafe_id).rows == [[1]]
    manifest_path = saved.root / "run.json"
    payload = json.loads(manifest_path.read_text())
    payload["profiles"][unsafe_id]["preview_path"] = "../outside.json"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid preview path"):
        saved.read_preview(unsafe_id)

    payload["profiles"][unsafe_id]["preview_path"] = saved.preview_path(unsafe_id)
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    preview_path = saved.root / saved.preview_path(unsafe_id)
    preview_path.unlink()
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    preview_path.symlink_to(outside)
    with pytest.raises(ValueError, match="escapes"):
        saved.read_preview(unsafe_id)
