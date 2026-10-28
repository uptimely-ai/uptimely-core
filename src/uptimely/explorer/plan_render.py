"""Render compiled execution-plan pages within the explorer website."""

from __future__ import annotations

import collections
import dataclasses
import json
import os
import pathlib
import typing

from uptimely import execution_plan, project_paths
from uptimely.spec import functions

from . import graph_render, render

PLAN_PAGES = render.WEBSITE_PAGES["plan"]
__all__ = [
    "PLAN_PAGES",
    "_invocation_label",
    "_invocation_label_lines",
    "_create_website_pages",
    "_render_step",
]


def _invocation_label(invocation: execution_plan.Invocation) -> str:
    """Format an invocation with its actual bound arguments."""
    arguments = ", ".join(
        f"{name}={json.dumps(value, ensure_ascii=False, separators=(',', ':'))}"
        for name, value in invocation.arguments.items()
    )
    return f"{invocation.function_id}({arguments})"


def _invocation_label_lines(invocation: execution_plan.Invocation) -> list[str]:
    """Return a multiline invocation signature with indented bound arguments."""
    if not invocation.arguments:
        return [f"{invocation.function_id}()"]

    arguments = list(invocation.arguments.items())
    lines = [f"{invocation.function_id}("]
    for index, (name, value) in enumerate(arguments):
        value_lines = json.dumps(value, ensure_ascii=False, indent=2).splitlines()
        argument_lines = [f"  {name}={value_lines[0]}"]
        argument_lines.extend(f"  {line}" for line in value_lines[1:])
        if index < len(arguments) - 1:
            argument_lines[-1] += ","
        lines.extend(argument_lines)
    lines.append(")")
    return lines


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
        "operation": invocation.function_kind,
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


def _create_website_pages(
    plan: execution_plan.ExecutionPlan,
    output_directory: pathlib.Path,
    *,
    index_filename: str = project_paths.EXPLORER_INDEX_FILE.name,
    project_name: str | None = None,
    execution_scope: str = "all features",
    is_scoped: bool = False,
) -> None:
    """Write linked overview, invocation graph, and stage pages for a plan.

    Args:
        plan: The compiled execution plan to render.
        output_directory: Directory shared by all website pages.
        index_filename: Filename of the website dashboard.
        project_name: Project title displayed in the shared top bar.
        execution_scope: Feature coverage of the rendered build.
        is_scoped: Whether the plan covers a selected feature subset.
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
    stage_by_invocation = {
        invocation.id: stage_number
        for stage_number, stage in enumerate(invocations_by_stage, start=1)
        for invocation in stage
    }
    graph_nodes = [
        {
            "id": invocation.id,
            "node_type": "invocation",
            "operation": invocation.function_kind,
            "stage": stage_by_invocation[invocation.id],
            "label": _invocation_label(invocation),
            "label_lines": _invocation_label_lines(invocation),
            "function_id": invocation.function_id,
            "mapping_id": invocation.mapping_id,
            "entity": invocation.entity_id,
            "dataset_id": invocation.dataset_id,
            "feature": (
                ", ".join(invocation.output_features)
                if invocation.function_kind in {functions.ESCAPE, functions.VECTORIZE}
                else None
            ),
            "input_features": invocation.input_features,
            "output_features": invocation.output_features,
            "dependency_ids": sorted(invocation.dependency_ids),
        }
        for invocation in sorted(plan.invocations, key=lambda item: item.id)
    ]
    graph_links = [
        {"source": dependency_id, "target": invocation.id}
        for invocation in plan.invocations
        for dependency_id in invocation.dependency_ids
    ]
    invocation_graph_data = json.dumps(
        {
            "nodes": graph_nodes,
            "links": sorted(graph_links, key=lambda link: (link["source"], link["target"])),
        }
    ).replace("</script>", r"<\/script>")

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

    environment = render.html_environment()
    graph_style = graph_render.GraphStyle()
    context = {
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
        "dependency_count": len(graph_links),
        "max_parallel_invocations": max((len(stage["steps"]) for stage in stages), default=0),
        "operation_counts": sorted(
            collections.Counter(invocation.function_kind for invocation in plan.invocations).items()
        ),
        "stages": stages,
        "invocation_graph_data": invocation_graph_data,
        "graph_style": graph_style,
        "graph_style_data": dataclasses.asdict(graph_style),
        "include_navigation": True,
        "active_page": "plan",
        "index_filename": index_filename,
        "project_name": project_name,
        "root_path": "../",
        "execution_scope": execution_scope,
        "is_scoped": is_scoped,
    }

    output_directory.mkdir(parents=True, exist_ok=True)
    for section, filename in PLAN_PAGES.items():
        document = environment.get_template(f"plan/{section}.html.j2").render(
            **context,
            active_section=section,
            section_title=section.title(),
        )
        target = output_directory / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(document, encoding="utf-8")
