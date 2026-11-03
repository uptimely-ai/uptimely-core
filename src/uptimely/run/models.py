"""Validated contracts for the latest run and its related artifacts."""

from __future__ import annotations

import hashlib
import json
import typing

import pydantic

from uptimely.engine import config
from uptimely.engine.runtime import result
from uptimely.execution_plan import serialization
from uptimely.project.build import models as build_models

LOG_FILE = "log.jsonl"
MANIFEST_FILE = "run.json"


class ArtifactModel(pydantic.BaseModel):
    """Reject unknown fields and non-finite numeric metadata."""

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class BuildIdentity(ArtifactModel):
    """Build provenance independent of subsequent on-disk bundle replacement."""

    fingerprint: str
    manifest: build_models.BuildManifest

    @classmethod
    def from_bundle(cls, bundle: build_models.BuildBundle) -> typing.Self:
        """Fingerprint the loaded spec, plan, and build manifest, not mutable paths."""
        payload = {
            "manifest": bundle.manifest.model_dump(mode="json"),
            "spec": bundle.spec_definition.model_dump(mode="json"),
            "plan": serialization.to_dict(bundle.execution_plan),
        }
        content = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return cls(
            fingerprint=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            manifest=bundle.manifest,
        )


class InvocationResult(ArtifactModel):
    """Status, execution duration, and optional failure for one planned invocation."""

    status: result.InvocationStatus
    duration_seconds: float | None = pydantic.Field(default=None, ge=0)
    error: str | None = None


class PreviewColumn(ArtifactModel):
    """Ordered physical column name and Polars dtype."""

    name: str
    dtype: str


class ProfilePreview(ArtifactModel):
    """A bounded head sample with explicit success or failure."""

    profile_id: str
    status: typing.Literal["succeeded", "failed"]
    requested_rows: int = pydantic.Field(gt=0)
    sampling: typing.Literal["head"] = "head"
    columns: list[PreviewColumn]
    rows: list[list[pydantic.JsonValue]]
    error: str | None = None

    @pydantic.model_validator(mode="after")
    def validate_sample(self) -> typing.Self:
        """Require rectangular bounded samples and explicit failure diagnostics."""
        if len(self.rows) > self.requested_rows:
            raise ValueError("Preview exceeds its requested row limit")
        if any(len(row) != len(self.columns) for row in self.rows):
            raise ValueError("Preview rows do not match the column schema")
        if (self.status == "failed") != (self.error is not None):
            raise ValueError("Only failed previews must have an error")
        if self.status == "failed" and (self.columns or self.rows):
            raise ValueError("Failed previews cannot contain sample data")
        return self


class ProfileSummary(ArtifactModel):
    """Cheap frame statistics and the location of its preview."""

    row_count: int | None = pydantic.Field(ge=0)
    column_count: int | None = pydantic.Field(ge=0)
    preview_path: str
    preview_status: typing.Literal["succeeded", "failed"]
    preview_error: str | None


class RunManifest(ArtifactModel):
    """One completed execution, including partial results after failure."""

    run_id: str
    started_at: pydantic.AwareDatetime
    finished_at: pydantic.AwareDatetime
    duration_seconds: float = pydantic.Field(ge=0)
    status: typing.Literal["succeeded", "failed", "interrupted"]
    error: str | None
    uptimely_version: str
    build: BuildIdentity
    engine: config.EngineConfig
    runtime_validation: bool
    preview_rows: int = pydantic.Field(gt=0)
    invocations: dict[str, InvocationResult]
    profiles: dict[str, ProfileSummary]
    log_path: typing.Literal["log.jsonl"] = LOG_FILE


class LogEntry(ArtifactModel):
    """A single structured log event, suitable for filtering in Explorer."""

    timestamp: pydantic.AwareDatetime
    level: str
    logger: str
    message: str
    invocation_id: str | None = None
    profile_id: str | None = None
    exception: str | None = None
