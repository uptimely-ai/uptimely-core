"""Prepare versioned, JSON-ready presentation data for the Explorer."""

from __future__ import annotations

import dataclasses
import enum
import json
import pathlib
import typing

from uptimely import execution_plan, spec
from uptimely.explorer.sections import data_lineage, feature_lineage
from uptimely.explorer.sections import plan as plan_section
from uptimely.explorer.sections import spec as spec_section

EXPLORER_FORMAT_VERSION = 1


class ExplorerPresentationData(typing.TypedDict):
    """Versioned data consumed by the Explorer frontend."""

    format_version: typing.Literal[1]
    project: dict[str, object]
    scope: dict[str, object]
    catalogs: dict[str, object]
    graphs: dict[str, object]
    plan: dict[str, object]
    animation: dict[str, object]


def _json_value(value: object) -> object:
    """Convert section models into ordinary JSON-compatible values."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _json_value(dataclasses.asdict(value))
    if isinstance(value, enum.Enum):
        return _json_value(value.value)
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Explorer presentation contains a non-JSON value: {type(value).__name__}")


def _graph_payload(value: object) -> dict[str, object]:
    """Decode a section graph payload into the containing JSON structure."""
    if not isinstance(value, str):
        raise TypeError("Explorer graph payload must be a serialized string")
    payload = json.loads(value)
    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("nodes"), list)
        or not isinstance(payload.get("links"), list)
    ):
        raise ValueError("Explorer graph payload must contain nodes and links")
    return payload


def build_presentation_data(
    spec_definition: spec.Spec,
    plan: execution_plan.ExecutionPlan,
    *,
    features: list[str] | None = None,
    output_directory: pathlib.Path = pathlib.Path("_generated/explorer"),
) -> ExplorerPresentationData:
    """Prepare complete Explorer presentation data without rendering or writing files.

    Args:
        spec_definition: Project specification used for catalog labels and metadata.
        plan: Compiled execution plan; analytical functions are not executed.
        features: Selected output features, or ``None`` for all features.
        output_directory: Explorer output location used to resolve source links.

    Returns:
        Versioned JSON-ready project, catalog, graph, plan, and animation data.
    """
    spec_data = spec_section.build_context(spec_section._build_context(spec_definition, False))
    feature_data = feature_lineage.build_context(spec.FeatureGraph(spec_definition))
    plan_data = plan_section.build_context(plan, output_directory, spec_definition)
    animation_data = data_lineage.build_context(spec_definition, plan)

    execution_scope = (
        "all features" if features is None else f"selected features: {', '.join(features)}"
    )
    result: ExplorerPresentationData = {
        "format_version": EXPLORER_FORMAT_VERSION,
        "project": {
            "name": spec_definition.name,
            "spec_version": spec_definition.spec_version,
        },
        "scope": {
            "label": execution_scope,
            "features": features,
            "is_scoped": features is not None,
        },
        "catalogs": {
            "configuration": spec_data["configuration"],
            "summary": spec_data["summary"],
            "feature_dependencies": spec_data["feature_dependencies"],
            "function_groups": spec_data["function_groups"],
        },
        "graphs": {
            "feature_lineage": _graph_payload(feature_data["graph_data"]),
            "feature_style": feature_data["graph_style_data"],
            "invocation_lineage": _graph_payload(plan_data["invocation_lineage_data"]),
            "invocation_style": plan_data["graph_style_data"],
        },
        "plan": {
            key: value
            for key, value in plan_data.items()
            if key not in {"stages", "invocation_lineage_data", "graph_style"}
        },
        "stages": plan_data["stages"],
        "animation": animation_data,
    }
    return typing.cast(ExplorerPresentationData, _json_value(result))


def validate_presentation_data(value: object) -> ExplorerPresentationData:
    """Validate the versioned structure expected by the Explorer frontend."""
    required_keys = {
        "format_version",
        "project",
        "scope",
        "catalogs",
        "graphs",
        "plan",
        "stages",
        "animation",
    }
    if not isinstance(value, dict):
        raise ValueError("Explorer presentation data must be an object")
    if (
        set(value) != required_keys
        or type(value.get("format_version")) is not int
        or value["format_version"] != EXPLORER_FORMAT_VERSION
    ):
        raise ValueError("Explorer presentation data has an unsupported schema")
    for key in ("project", "scope", "catalogs", "graphs", "plan", "animation"):
        if not isinstance(value[key], dict):
            raise ValueError(f"Explorer presentation field {key!r} must be an object")
    if not isinstance(value["stages"], list):
        raise ValueError("Explorer presentation field 'stages' must be a list")
    return typing.cast(ExplorerPresentationData, value)


def serialize_presentation_data(data: ExplorerPresentationData) -> str:
    """Validate and serialize an Explorer presentation snapshot."""
    data = validate_presentation_data(data)
    return json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)
