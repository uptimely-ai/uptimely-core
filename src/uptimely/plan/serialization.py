"""JSON serialization and file I/O for portable execution plans."""

from __future__ import annotations

import json
import pathlib
import typing

from . import models


def to_dict(plan: models.ExecutionPlan) -> dict[str, typing.Any]:
    """Return a plan as JSON-compatible data."""
    return plan.model_dump(mode="json")


def from_dict(payload: dict[str, typing.Any]) -> models.ExecutionPlan:
    """Load a plan from a decoded JSON object."""
    if not isinstance(payload, dict):
        raise ValueError("Plan artifact must contain a JSON object")
    return models.ExecutionPlan.model_validate(payload)


def export_json(plan: models.ExecutionPlan, path: str | pathlib.Path) -> pathlib.Path:
    """Serialize a plan to a JSON file."""
    target = pathlib.Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(to_dict(plan), indent=2), encoding="utf-8")
    return target


def from_json(path: str | pathlib.Path) -> models.ExecutionPlan:
    """Deserialize a plan from a JSON file."""
    payload = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    return from_dict(payload)
