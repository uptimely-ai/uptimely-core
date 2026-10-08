"""Serialization helpers for portable execution plans."""

from pathlib import Path

from .models import ExecutionPlan, Plan


def export_json(plan: Plan | ExecutionPlan, path: str | Path) -> Path:
    """Serialize a plan to JSON."""
    execution_plan = plan if isinstance(plan, ExecutionPlan) else ExecutionPlan(plan)
    return execution_plan.export_json(path)


def from_json(path: str | Path) -> ExecutionPlan:
    """Deserialize an execution plan from JSON."""
    return ExecutionPlan.from_json(path)
