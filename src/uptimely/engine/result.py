"""Explicit results returned by plan execution."""

from __future__ import annotations

import dataclasses
import typing

type CallableStatus = typing.Literal["succeeded", "failed", "skipped"]


@dataclasses.dataclass(frozen=True)
class ExecutionResult:
    """Immutable summary and outputs produced by one engine execution."""

    datasets: dict[str, object]
    calculated_outputs: dict[tuple[str, str], object]
    callable_statuses: dict[str, CallableStatus]
    durations: dict[str, float]
    failures: dict[str, str]
    plan_version: int
