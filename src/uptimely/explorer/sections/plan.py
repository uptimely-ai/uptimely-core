"""Render compiled execution-plan pages within the explorer website."""

from __future__ import annotations

import collections
import dataclasses
import os
import pathlib
import typing

from uptimely import execution_plan
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
            title="Invocation lineage" if section == "invocation_lineage" else section.title(),
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
    invocations_by_id: typing.Mapping[str, execution_plan.Invocation] | None = None,
) -> dict[str, typing.Any]:
    """Build the display model used by the execution-plan HTML templates."""
    if invocations_by_id is None:
        invocations_by_id = plan.invocations_by_id

    def display_value(value: object) -> object:
        if isinstance(value, dict):
            if "type" in value and "value" in value:
                return display_value(value["value"])
            return {name: display_value(item) for name, item in value.items()}
        if isinstance(value, list):
            return [display_value(item) for item in value]
        return value

    return {
        "position": position,
        "function": invocation.function_id,
        "function_kind": invocation.function_kind,
        "title": invocation.function_id.replace("_", " ").capitalize(),
        "entrypoint": invocation.entrypoint,
        "entity": invocation.entity_id,
        "dataset": invocation.dataset_id,
        "feature": ", ".join(invocation.output_features)
        if invocation.function_kind in {functions.COLLAPSE, functions.ESCAPE, functions.VECTORIZE}
        else None,
        "input_features": invocation.input_features,
        "output_features": invocation.output_features,
        "uncontrolled": invocation.function_kind == functions.ESCAPE,
        "row_context": invocation.row_context.to_dict() if invocation.row_context else None,
        "depends_on_invocations": [
            {"function": invocations_by_id[dependency_id].function_id}
            for dependency_id in invocation.dependency_ids
        ],
        "args": {
            name: {
                "type": {
                    "binding": value.get("type") if isinstance(value, dict) else None,
                    "function": None,
                    "engine": None,
                },
                "value": display_value(
                    value.get("value") if isinstance(value, dict) and "type" in value else value
                ),
            }
            for name, value in invocation.arguments.items()
        },
        "returns": {"type": {"engine": plan.resources.get("signatures", {}).get(invocation.id)}},
    }


def build_context(
    plan: execution_plan.ExecutionPlan,
    output_directory: pathlib.Path,
) -> dict[str, object]:
    """Prepare overview, invocation-lineage, and stage data without rendering or writing pages.

    Args:
        plan: The compiled execution plan to render.
        output_directory: Website directory used to resolve relative source links.

    Returns:
        Display data shared by the plan pages.
    """
    invocations_by_stage = plan.execution_stages
    invocations_in_order = [invocation for stage in invocations_by_stage for invocation in stage]
    invocations_by_id = {invocation.id: invocation for invocation in invocations_in_order}
    position_by_invocation = {
        invocation.id: position for position, invocation in enumerate(invocations_in_order, start=1)
    }
    stages = [
        {
            "stage": stage_number,
            "steps": [
                _render_step(
                    position_by_invocation[invocation.id],
                    invocation,
                    plan,
                    invocations_by_id,
                )
                for invocation in stage
            ],
        }
        for stage_number, stage in enumerate(invocations_by_stage, start=1)
    ]
    steps = [step for stage in stages for step in stage["steps"]]
    invocation_nodes, invocation_links = invocation_lineage.invocation_lineage_payload(plan)
    invocation_lineage_data = common.serialize_graph_payload(invocation_nodes, invocation_links)

    for stage in stages:
        stage["steps"].sort(
            key=lambda step: (
                step["entrypoint"] or "",
                step["entity"],
                step["dataset"] or "",
                step["feature"] or "",
            )
        )
        for step in stage["steps"]:
            step["depends_on_invocations"].sort(key=lambda dependency: dependency["function"])
            entrypoint = step["entrypoint"]
            source_path = entrypoint.partition(":")[0] if entrypoint else None
            if source_path and not source_path.endswith(".py"):
                source_path = source_path.replace(".", "/") + ".py"
            step["source_href"] = (
                pathlib.Path(
                    os.path.relpath(source_path, start=output_directory / "plan")
                ).as_posix()
                if source_path
                else None
            )

    graph_style = graph_style_module.GraphStyle()
    return {
        "plan_version": plan.plan_version,
        "invocation_count": len(plan.invocations),
        "function_count": len({step["function"] for step in steps}),
        "entity_count": len({invocation.entity_id for invocation in invocations_in_order}),
        "feature_count": len(
            {
                feature
                for invocation in plan.invocations
                if invocation.function_kind == functions.VECTORIZE
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
