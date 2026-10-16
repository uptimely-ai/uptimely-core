"""Serialization helpers for portable execution plans."""

import pathlib

from . import models


def export_json(plan: models.Plan | models.ExecutionPlan, path: str | pathlib.Path) -> pathlib.Path:
    """Serialize a plan to JSON."""
    execution_plan = plan if isinstance(plan, models.ExecutionPlan) else models.ExecutionPlan(plan)
    return execution_plan.export_json(path)


def from_json(path: str | pathlib.Path) -> models.ExecutionPlan:
    """Deserialize an execution plan from JSON."""
    return models.ExecutionPlan.from_json(path)
