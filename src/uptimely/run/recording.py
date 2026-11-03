"""Record execution metadata, structured logs, and bounded profile samples."""

from __future__ import annotations

import contextlib
import dataclasses
import datetime
import importlib.metadata
import logging
import pathlib
import threading
import time
import types
import typing
import uuid

import polars as pl

from uptimely.engine import config
from uptimely.engine.runtime import result as result_module
from uptimely.project.build import models as build_models

from . import models, preview, store

logger = logging.getLogger(__name__)


class RunLogHandler(logging.Handler):
    """Stream this execution thread's Python log records as JSONL."""

    def __init__(self, path: pathlib.Path) -> None:
        self._stream = path.open("w", encoding="utf-8")
        super().__init__()
        self._thread = threading.get_ident()

    def emit(self, record: logging.LogRecord) -> None:
        """Write and flush explicitly; filesystem failures must propagate."""
        if threading.get_ident() != self._thread:
            return
        entry = models.LogEntry(
            timestamp=datetime.datetime.fromtimestamp(record.created, datetime.UTC),
            level=record.levelname,
            logger=record.name,
            message=record.getMessage(),
            invocation_id=getattr(record, "invocation_id", None),
            profile_id=getattr(record, "profile_id", None),
            exception=(
                logging.Formatter().formatException(record.exc_info) if record.exc_info else None
            ),
        )
        self._stream.write(entry.model_dump_json() + "\n")
        self._stream.flush()

    def close(self) -> None:
        """Close the stream when the scoped handler is removed."""
        self._stream.close()
        super().close()


class RunRecorder:
    """Scope log capture and publish one complete run after execution finishes."""

    def __init__(
        self,
        bundle: build_models.BuildBundle,
        settings: config.EngineConfig,
        *,
        validate: bool,
        preview_rows: int,
    ) -> None:
        if isinstance(preview_rows, bool) or not isinstance(preview_rows, int) or preview_rows <= 0:
            raise ValueError("preview_rows must be a positive integer")
        self._bundle = bundle
        self._settings = settings
        self._validate = validate
        self._preview_rows = preview_rows
        self._store = store.RunStore(bundle.project_root)
        self._resources = contextlib.ExitStack()
        self._logs = contextlib.ExitStack()
        self.result: result_module.ExecutionResult | None = None
        self._profile_summaries: dict[str, models.ProfileSummary] = {}
        self._preview_frames: dict[str, object] = {}
        self._preview_failures: dict[str, str] = {}

    def __enter__(self) -> typing.Self:
        """Prepare staging and start scoped logging before analytical execution."""
        with contextlib.ExitStack() as resources:
            self._staging = resources.enter_context(self._store.staging())
            self._identity = models.BuildIdentity.from_bundle(self._bundle)
            handler = RunLogHandler(self._staging / models.LOG_FILE)
            resources.callback(self._logs.close)
            self._logs.callback(handler.close)
            root_logger = logging.getLogger()
            root_logger.addHandler(handler)
            self._logs.callback(root_logger.removeHandler, handler)
            self._started_at = datetime.datetime.now(datetime.UTC)
            self._started = time.perf_counter()
            self._resources = resources.pop_all()
        return self

    def finish(self, result: result_module.ExecutionResult) -> result_module.ExecutionResult:
        """Stop the execution clock and collect previews once for disk and callers."""
        self._finished_at = datetime.datetime.now(datetime.UTC)
        self._duration = time.perf_counter() - self._started
        self.result = result
        self._profile_summaries = self._profiles()
        return dataclasses.replace(
            result,
            duration_seconds=self._duration,
            preview_frames=self._preview_frames,
            preview_failures=self._preview_failures,
        )

    def __exit__(
        self,
        error_type: type[BaseException] | None,
        error: BaseException | None,
        traceback: types.TracebackType | None,
    ) -> None:
        """Save failed or successful execution, without swallowing exceptions."""
        with self._resources:
            finished_at = (
                self._finished_at
                if self.result is not None
                else datetime.datetime.now(datetime.UTC)
            )
            duration = (
                self._duration if self.result is not None else time.perf_counter() - self._started
            )
            if error is not None:
                logger.error("Run failed: %s", error, exc_info=(error_type, error, traceback))
            manifest = self._manifest(finished_at, duration, error)
            self._logs.close()
            (self._staging / models.MANIFEST_FILE).write_text(
                manifest.model_dump_json(indent=2), encoding="utf-8"
            )
            self._store.publish(self._staging)

    def _profiles(self) -> dict[str, models.ProfileSummary]:
        profiles: dict[str, models.ProfileSummary] = {}
        if self.result is None:
            return profiles
        for profile_id, frame in self.result.main_frames.items():
            try:
                sample, collected = preview.collect_preview(profile_id, frame, self._preview_rows)
                self._preview_frames[profile_id] = collected
            except (
                pl.exceptions.PolarsError,
                TypeError,
                ValueError,
                RuntimeError,
                OSError,
                ArithmeticError,
            ) as error:
                message = f"{type(error).__name__}: {error}"
                logger.exception(
                    "Preview for profile %s failed: %s",
                    profile_id,
                    error,
                    extra={"profile_id": profile_id},
                )
                sample = models.ProfilePreview(
                    profile_id=profile_id,
                    status="failed",
                    requested_rows=self._preview_rows,
                    columns=[],
                    rows=[],
                    error=message,
                )
                self._preview_failures[profile_id] = message
            relative_path = self._store.preview_path(profile_id)
            path = self._staging / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(sample.model_dump_json(indent=2), encoding="utf-8")
            profiles[profile_id] = models.ProfileSummary(
                row_count=frame.height if isinstance(frame, pl.DataFrame) else None,
                column_count=len(sample.columns) if sample.status == "succeeded" else None,
                preview_path=relative_path,
                preview_status=sample.status,
                preview_error=sample.error,
            )
        return profiles

    def _manifest(
        self, finished_at: datetime.datetime, duration: float, error: BaseException | None
    ) -> models.RunManifest:
        statuses = self.result.invocation_statuses if self.result is not None else {}
        durations = self.result.durations if self.result is not None else {}
        failures = self.result.failures if self.result is not None else {}
        status: typing.Literal["succeeded", "failed", "interrupted"] = "succeeded"
        if error is not None or failures:
            status = (
                "interrupted" if isinstance(error, (KeyboardInterrupt, SystemExit)) else "failed"
            )
        return models.RunManifest(
            run_id=uuid.uuid4().hex,
            started_at=self._started_at,
            finished_at=finished_at,
            duration_seconds=duration,
            status=status,
            error=f"{type(error).__name__}: {error}" if error is not None else None,
            uptimely_version=importlib.metadata.version("uptimely-core"),
            build=self._identity,
            engine=self._settings,
            runtime_validation=self._validate,
            preview_rows=self._preview_rows,
            invocations={
                invocation.id: models.InvocationResult(
                    status=statuses.get(invocation.id, "skipped"),
                    duration_seconds=durations.get(invocation.id),
                    error=failures.get(invocation.id),
                )
                for invocation in self._bundle.execution_plan.invocations
            },
            profiles=self._profile_summaries,
        )
