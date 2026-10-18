"""Render compiled execution-plan pages within the explorer website."""

from __future__ import annotations

import collections
import json
import os
import pathlib
import typing

from uptimely import project
from uptimely import render as uptimely_render
from uptimely.compiler import plan as uptimely_plan

from . import graph_render

PLAN_PAGES = uptimely_render.WEBSITE_PAGES["plan"]
__all__ = [
    "PLAN_PAGES",
    "_callable_label",
    "_callable_label_lines",
    "_create_website_pages",
    "_render_step",
]


def _callable_label(callable: uptimely_plan.Callable) -> str:
    """Format a callable identifier with its actual bound arguments."""
    arguments = ", ".join(
        f"{name}={json.dumps(value, ensure_ascii=False, separators=(',', ':'))}"
        for name, value in callable.arguments.items()
    )
    return f"{callable.function_id}({arguments})"


def _callable_label_lines(callable: uptimely_plan.Callable) -> list[str]:
    """Return a multiline callable signature with indented bound arguments."""
    if not callable.arguments:
        return [f"{callable.function_id}()"]

    arguments = list(callable.arguments.items())
    lines = [f"{callable.function_id}("]
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
    position: int, callable: uptimely_plan.Callable, plan: uptimely_plan.ExecutionPlan
) -> dict[str, typing.Any]:
    """Build the display model used by the execution-plan HTML templates."""

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
        "function": callable.function_id,
        "operation": callable.operation,
        "title": callable.function_id.replace("_", " ").capitalize(),
        "entrypoint": callable.entrypoint,
        "entity": callable.entity_id,
        "dataset": callable.dataset_id,
        "feature": (
            ", ".join(callable.output_features)
            if callable.operation == "collapse"
            else callable.output
            if callable.operation == "vectorize"
            else None
        ),
        "row_context": callable.row_context.to_dict() if callable.row_context else None,
        "depends_on_callables": [
            {
                "function": dependency.split(":")[2]
                if dependency.startswith("callable:")
                else dependency
            }
            for dependency in callable.dependency_ids
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
            for name, value in callable.arguments.items()
        },
        "returns": {"type": {"engine": plan.plan.resources.get("signatures", {}).get(callable.id)}},
    }


def _create_website_pages(
    plan: uptimely_plan.ExecutionPlan,
    output_directory: pathlib.Path,
    *,
    index_filename: str = project.EXPLORER_INDEX_FILE.name,
) -> None:
    """Write linked overview, callable graph, and stage pages for a plan.

    Args:
        plan: The compiled execution plan to render.
        output_directory: Directory shared by all website pages.
        index_filename: Filename of the website dashboard.
    """
    callables_by_stage = plan.execution_stages
    callables_in_order = [callable for stage in callables_by_stage for callable in stage]
    position_by_callable = {
        callable.id: position for position, callable in enumerate(callables_in_order, start=1)
    }
    stages = [
        {
            "stage": stage_number,
            "steps": [
                _render_step(position_by_callable[callable.id], callable, plan)
                for callable in stage
            ],
        }
        for stage_number, stage in enumerate(callables_by_stage, start=1)
    ]
    steps = [step for stage in stages for step in stage["steps"]]
    stage_by_callable = {
        callable.id: stage_number
        for stage_number, stage in enumerate(callables_by_stage, start=1)
        for callable in stage
    }
    graph_nodes = [
        {
            "id": callable.id,
            "node_type": "callable",
            "operation": callable.operation,
            "stage": stage_by_callable[callable.id],
            "label": _callable_label(callable),
            "label_lines": _callable_label_lines(callable),
            "function_id": callable.function_id,
            "entity": callable.entity_id,
            "dataset_id": callable.dataset_id,
            "feature": callable.output if callable.operation == "vectorize" else None,
            "dependency_ids": sorted(callable.dependency_ids),
        }
        for callable in sorted(plan.callables, key=lambda callable: callable.id)
    ]
    graph_links = [
        {"source": dependency_id, "target": callable.id}
        for callable in plan.callables
        for dependency_id in callable.dependency_ids
    ]
    callable_graph_data = json.dumps(
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
            step["depends_on_callables"].sort(key=lambda dependency: dependency["function"])
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

    environment = uptimely_render.html_environment()
    context = {
        "plan_version": plan.plan.plan_version,
        "callable_count": len(plan.callables),
        "function_count": len({step["function"] for step in steps}),
        "entity_count": len({callable.entity_id for callable in callables_in_order}),
        "feature_count": len(
            {
                callable.output
                for callable in plan.callables
                if callable.operation == "vectorize" and callable.output is not None
            }
        ),
        "stage_count": len(stages),
        "dependency_count": len(graph_links),
        "max_parallel_callables": max((len(stage["steps"]) for stage in stages), default=0),
        "operation_counts": sorted(
            collections.Counter(callable.operation for callable in plan.callables).items()
        ),
        "stages": stages,
        "callable_graph_data": callable_graph_data,
        "graph_style": graph_render.GraphStyle(),
        "include_navigation": True,
        "active_page": "plan",
        "index_filename": index_filename,
        "root_path": "../",
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
