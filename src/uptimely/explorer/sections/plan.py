"""Render compiled execution-plan pages within the explorer website."""

from __future__ import annotations

import collections
import dataclasses
import os
import pathlib
import typing

from uptimely import execution_plan, spec
from uptimely.explorer import common, render
from uptimely.explorer import graph_style as graph_style_module
from uptimely.spec import functions

from . import invocation_lineage

PLAN_PAGES = render.WEBSITE_PAGES["plan"]
SECTION = render.WebsiteSection(
    active_page="plan",
    pages=tuple(
        render.WebsitePage(
            f"plan/{section}.html.j2",
            filename,
            active_section=section,
            title="Topology" if section == "invocation_lineage" else section.title(),
        )
        for section, filename in PLAN_PAGES.items()
    ),
)
__all__ = [
    "PLAN_PAGES",
    "SECTION",
    "build_context",
    "_render_step",
]


def _render_step(
    position: int,
    invocation: execution_plan.Invocation,
    plan: execution_plan.ExecutionPlan,
    spec_definition: spec.Spec,
    invocations_by_id: typing.Mapping[str, execution_plan.Invocation] | None = None,
    feature_labels: typing.Mapping[str, str] | None = None,
) -> dict[str, typing.Any]:
    """Build a plan step's display model, optionally reusing lookup indexes."""
    if spec_definition is None:
        raise ValueError("spec_definition is required to render plan steps")
    if invocations_by_id is None:
        invocations_by_id = plan.invocations_by_id
    if feature_labels is None:
        feature_labels = common.feature_labels(spec_definition)

    function_name = spec_definition.functions[invocation.function_id].name or invocation.function_id
    entity = spec_definition.entities[invocation.entity_id]
    dataset = (
        entity.datasets.get(invocation.dataset_id) if invocation.dataset_id is not None else None
    )
    input_labels = [feature_labels.get(name, name) for name in invocation.input_features]
    output_labels = [feature_labels.get(name, name) for name in invocation.output_features]
    kind = functions.FUNCTION_KINDS[invocation.function_kind]
    displayed_feature = (
        ", ".join(output_labels)
        if kind.is_effect or kind.is_transformer or kind.dimension_change == "remove"
        else None
    )
    return {
        "position": position,
        "function": invocation.function_id,
        "function_kind": invocation.function_kind,
        "title": function_name,
        "function_label": function_name,
        "entrypoint": invocation.entrypoint,
        "entity": invocation.entity_id,
        "dataset": invocation.dataset_id,
        "dataset_label": (
            dataset.name or invocation.dataset_id if dataset is not None else invocation.dataset_id
        ),
        "feature": displayed_feature,
        "input_features": input_labels,
        "output_features": output_labels,
        "input_feature_ids": invocation.input_features,
        "output_feature_ids": invocation.output_features,
        "uncontrolled": kind.is_effect,
        "row_context": invocation.row_context.to_dict() if invocation.row_context else None,
        "depends_on_invocations": [
            {
                "function": (
                    spec_definition.functions[invocations_by_id[dependency_id].function_id].name
                )
            }
            for dependency_id in invocation.dependency_ids
        ],
        "args": {
            name: {
                "type": {
                    "binding": value.get("type") if isinstance(value, dict) else None,
                    "function": None,
                    "engine": None,
                },
                "value": _display_value(
                    value.get("value") if isinstance(value, dict) and "type" in value else value
                ),
            }
            for name, value in invocation.arguments.items()
        },
        "returns": {"type": {"engine": plan.resources.get("signatures", {}).get(invocation.id)}},
    }


def _display_value(value: object) -> object:
    """Unwrap typed argument values while retaining nested containers."""
    if isinstance(value, dict):
        if "type" in value and "value" in value:
            return _display_value(value["value"])
        return {name: _display_value(item) for name, item in value.items()}
    if isinstance(value, list):
        return [_display_value(item) for item in value]
    return value


def _source_href(entrypoint: str, output_directory: pathlib.Path) -> str | None:
    """Resolve a module or file entrypoint relative to the plan pages."""
    if not entrypoint:
        return None
    source_path = entrypoint.partition(":")[0]
    if not source_path:
        return None
    if not source_path.endswith(".py"):
        source_path = source_path.replace(".", "/") + ".py"
    return pathlib.Path(os.path.relpath(source_path, start=output_directory / "plan")).as_posix()


def _step_sort_key(step: dict[str, typing.Any]) -> tuple[str, str, str, str]:
    """Keep stage cards in their existing display order."""
    return (
        step["entrypoint"] or "",
        step["entity"],
        step["dataset"] or "",
        step["feature"] or "",
    )


def build_context(
    plan: execution_plan.ExecutionPlan,
    output_directory: pathlib.Path,
    spec_definition: spec.Spec,
) -> dict[str, object]:
    """Prepare overview, invocation-lineage, and stage data without rendering or writing pages.

    Args:
        plan: The compiled execution plan to render.
        output_directory: Website directory used to resolve relative source links.
        spec_definition: Spec model for display-name resolution.

    Returns:
        Display data shared by the plan pages.
    """
    if spec_definition is None:
        raise ValueError("spec_definition is required to render the execution plan")
    invocations_by_stage = plan.execution_stages
    invocations_by_id = plan.invocations_by_id
    feature_labels = common.feature_labels(spec_definition)
    stages: list[dict[str, typing.Any]] = []
    position = 0
    for stage_number, stage in enumerate(invocations_by_stage, start=1):
        steps = []
        for invocation in stage:
            position += 1
            step = _render_step(
                position, invocation, plan, spec_definition, invocations_by_id, feature_labels
            )
            step["source_href"] = _source_href(invocation.entrypoint, output_directory)
            step["depends_on_invocations"].sort(key=lambda dependency: dependency["function"])
            steps.append(step)
        stages.append({"stage": stage_number, "steps": sorted(steps, key=_step_sort_key)})

    invocation_nodes, invocation_links = invocation_lineage.invocation_lineage_payload(
        plan, spec_definition, feature_labels
    )
    invocation_lineage_data = common.serialize_graph_payload(invocation_nodes, invocation_links)

    graph_style = graph_style_module.GraphStyle()
    return {
        "plan_version": plan.plan_version,
        "invocation_count": len(plan.invocations),
        "function_count": len({invocation.function_id for invocation in plan.invocations}),
        "entity_count": len({invocation.entity_id for invocation in plan.invocations}),
        "feature_count": len(
            {
                feature
                for invocation in plan.invocations
                if functions.FUNCTION_KINDS[invocation.function_kind].is_transformer
                for feature in invocation.output_features
            }
        ),
        "stage_count": len(stages),
        "dependency_count": len(invocation_links),
        "max_parallel_invocations": max((len(stage["steps"]) for stage in stages), default=0),
        "function_kind_counts": sorted(
            collections.Counter(invocation.function_kind for invocation in plan.invocations).items()
        ),
        "stages": stages,
        "invocation_lineage_data": invocation_lineage_data,
        "graph_style": graph_style,
        "graph_style_data": dataclasses.asdict(graph_style),
    }
