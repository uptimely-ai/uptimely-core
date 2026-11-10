"""JSON serialization and file I/O for portable execution plans."""

from __future__ import annotations

import json
import pathlib
import typing

from . import models


def to_dict(plan: models.ExecutionPlan) -> dict[str, typing.Any]:
    """Return a plan as JSON-compatible data."""
    return {
        "plan_version": plan.plan_version,
        "required_backend": plan.required_backend,
        "invocations": [
            {
                "id": invocation.id,
                "role": invocation.role,
                "result": invocation.result,
                "operator_kind": invocation.operator_kind,
                "produces_features": invocation.produces_features,
                "is_sink": invocation.is_sink,
                "dataframe_input_scope": invocation.dataframe_input_scope,
                "fragment_dimensions": invocation.fragment_dimensions,
                "row_count_relation": invocation.row_count_relation,
                "key_relation": invocation.key_relation,
                "row_order_relation": invocation.row_order_relation,
                "existing_data_relation": invocation.existing_data_relation,
                "entrypoint": invocation.entrypoint,
                "function_id": invocation.function_id,
                "operator_id": invocation.operator_id,
                "profile_id": invocation.profile_id,
                "arguments": invocation.arguments,
                "dependency_ids": invocation.dependency_ids,
                "output_features": invocation.output_features,
                "input_features": invocation.input_features,
                "target_identifiers": invocation.target_identifiers,
                "fragment_keys": invocation.fragment_keys,
                "output_types": invocation.output_types,
                "column_types": invocation.column_types,
                "argument_types": invocation.argument_types,
                "return_type": invocation.return_type,
                "package": (
                    invocation.package.model_dump() if invocation.package is not None else None
                ),
                "row_context": (
                    invocation.row_context.to_dict() if invocation.row_context is not None else None
                ),
            }
            for invocation in plan.invocations
        ],
        "stages": [stage.invocation_ids for stage in plan.stages],
    }


def from_dict(payload: dict[str, typing.Any]) -> models.ExecutionPlan:
    """Load a plan from a decoded JSON object."""
    if "plan_version" in payload:
        models._validate_plan_version(payload["plan_version"])
    required = {
        "plan_version",
        "required_backend",
        "invocations",
        "stages",
    }
    missing = sorted(required - payload.keys())
    if missing:
        raise ValueError("Plan is missing required fields: " + ", ".join(missing))
    unexpected = sorted(payload.keys() - required)
    if unexpected:
        raise ValueError("Plan contains unknown fields: " + ", ".join(unexpected))
    invocations = []
    for invocation in payload["invocations"]:
        missing_metadata = {
            "target_identifiers",
            "fragment_keys",
            "output_types",
            "produces_features",
            "is_sink",
            "dataframe_input_scope",
            "fragment_dimensions",
            "row_count_relation",
            "key_relation",
            "row_order_relation",
            "existing_data_relation",
            "column_types",
            "argument_types",
            "return_type",
            "package",
        } - invocation.keys()
        if missing_metadata:
            raise ValueError(
                f"Invocation {invocation.get('id', '<unknown>')} is missing runtime metadata: "
                + ", ".join(sorted(missing_metadata))
                + ". Recompile the project build."
            )
        invocations.append(models.Invocation(**invocation))
    return models.ExecutionPlan(
        plan_version=payload["plan_version"],
        required_backend=payload["required_backend"],
        invocations=invocations,
        stages=payload["stages"],
    )


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
