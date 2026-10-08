"""Explicit results returned by plan execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExecutionResult:
    """Immutable summary and outputs produced by one engine execution."""

    datasets: dict[tuple[str, str], object]
    calculated_outputs: dict[tuple[str, str, str], object]
    operation_statuses: dict[str, str]
    durations: dict[str, float]
    failures: dict[str, str]
    plan_version: str
    _calculations: dict[tuple[str, str, str], Any] = field(
        default_factory=dict, repr=False, compare=False
    )
