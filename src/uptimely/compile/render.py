"""Render compiled execution-plan pages within the explorer website."""

from __future__ import annotations

import collections
import json
import os
import pathlib
import typing

from uptimely import plan as uptimely_plan
from uptimely import render as uptimely_render
from uptimely.analytics import graph_render as render

from . import compiler

PLAN_PAGES = uptimely_render.WEBSITE_PAGES["plan"]


def _callable_label(operation: uptimely_plan.Operation) -> str:
    """Format a callable identifier with its actual bound arguments."""
    arguments = ", ".join(
        f"{name}={json.dumps(value, ensure_ascii=False, separators=(',', ':'))}"
        for name, value in operation.arguments.items()
    )
    return f"{operation.function_id}({arguments})"


def _callable_label_lines(operation: uptimely_plan.Operation) -> list[str]:
    """Return a multiline callable signature with indented bound arguments."""
    if not operation.arguments:
        return [f"{operation.function_id}()"]

    arguments = list(operation.arguments.items())
    lines = [f"{operation.function_id}("]
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
    position: int, operation: uptimely_plan.Operation, plan: compiler.ExecutionPlan
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
        "function": operation.function_id,
        "operation_type": operation.kind,
        "callable_type": operation.kind,
        "title": operation.function_id.replace("_", " ").capitalize(),
        "entrypoint": operation.entrypoint,
        "entity": operation.entity_id,
        "dataset": operation.dataset_id,
        "feature": (
            ", ".join(operation.output_features)
            if operation.kind == "collapse"
            else operation.output
            if operation.kind == "vectorize"
            else None
        ),
        "row_context": operation.row_context.to_dict() if operation.row_context else None,
        "depends_on_callables": [
            {
                "function": dependency.split(":")[2]
                if dependency.startswith("callable:")
                else dependency
            }
            for dependency in operation.dependency_ids
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
            for name, value in operation.arguments.items()
        },
        "returns": {
            "type": {"engine": plan.plan.resources.get("signatures", {}).get(operation.id)}
        },
    }


def _create_website_pages(
    plan: compiler.ExecutionPlan,
    output_directory: pathlib.Path,
    *,
    index_filename: str = "index.html",
) -> None:
    """Write linked overview, callable graph, and stage pages for a plan.

    Args:
        plan: The compiled execution plan to render.
        output_directory: Directory shared by all website pages.
        index_filename: Filename of the website dashboard.
    """
    operations_by_stage = plan.execution_stages
    operations_in_order = [operation for stage in operations_by_stage for operation in stage]
    position_by_operation = {
        operation.id: position for position, operation in enumerate(operations_in_order, start=1)
    }
    stages = [
        {
            "stage": stage_number,
            "steps": [
                _render_step(position_by_operation[operation.id], operation, plan)
                for operation in stage
            ],
        }
        for stage_number, stage in enumerate(operations_by_stage, start=1)
    ]
    steps = [step for stage in stages for step in stage["steps"]]
    stage_by_operation = {
        operation.id: stage_number
        for stage_number, stage in enumerate(operations_by_stage, start=1)
        for operation in stage
    }
    graph_nodes = [
        {
            "id": operation.id,
            "node_type": "callable",
            "operation_type": operation.kind,
            "callable_type": operation.kind,
            "stage": stage_by_operation[operation.id],
            "label": _callable_label(operation),
            "label_lines": _callable_label_lines(operation),
            "function_id": operation.function_id,
            "entity": operation.entity_id,
            "dataset_id": operation.dataset_id,
            "feature": operation.output if operation.kind == "vectorize" else None,
            "dependency_ids": sorted(operation.dependency_ids),
        }
        for operation in sorted(plan.operations, key=lambda operation: operation.id)
    ]
    graph_links = [
        {"source": dependency_id, "target": operation.id}
        for operation in plan.operations
        for dependency_id in operation.dependency_ids
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
        "analytics_version": plan.plan.analytics_version,
        "callable_count": len(plan.operations),
        "function_count": len({step["function"] for step in steps}),
        "entity_count": len({operation.entity_id for operation in operations_in_order}),
        "feature_count": len(
            {
                operation.output
                for operation in plan.operations
                if operation.kind == "vectorize" and operation.output is not None
            }
        ),
        "stage_count": len(stages),
        "dependency_count": len(graph_links),
        "max_parallel_operations": max((len(stage["steps"]) for stage in stages), default=0),
        "operation_counts": sorted(
            collections.Counter(operation.kind for operation in plan.operations).items()
        ),
        "stages": stages,
        "callable_graph_data": callable_graph_data,
        "graph_style": render.GraphStyle(),
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
