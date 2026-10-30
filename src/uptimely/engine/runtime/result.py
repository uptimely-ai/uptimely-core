"""Explicit results returned by plan execution."""

from __future__ import annotations

import dataclasses
import typing

type InvocationStatus = typing.Literal["succeeded", "failed", "skipped"]

INVOCATION_STATUS_SUCCEEDED: typing.Literal["succeeded"] = "succeeded"
INVOCATION_STATUS_FAILED: typing.Literal["failed"] = "failed"
INVOCATION_STATUS_SKIPPED: typing.Literal["skipped"] = "skipped"


@dataclasses.dataclass(frozen=True)
class ExecutionResult:
    """Immutable summary and outputs produced by one engine execution."""

    datasets: dict[str, object]
    calculated_outputs: dict[tuple[str, str], object]
    invocation_statuses: dict[str, InvocationStatus]
    durations: dict[str, float]
    failures: dict[str, str]
    plan_version: int
