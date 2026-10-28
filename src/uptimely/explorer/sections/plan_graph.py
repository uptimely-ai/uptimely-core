"""Prepare graph payloads for compiled execution plans."""

import json
import typing

from uptimely import execution_plan
from uptimely.spec import functions


def invocation_label(invocation: execution_plan.Invocation) -> str:
    """Format an invocation with its actual bound arguments."""
    arguments = ", ".join(
        f"{name}={json.dumps(value, ensure_ascii=False, separators=(',', ':'))}"
        for name, value in invocation.arguments.items()
    )
    return f"{invocation.function_id}({arguments})"


def invocation_label_lines(invocation: execution_plan.Invocation) -> list[str]:
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


def plan_graph_payload(
    plan: execution_plan.ExecutionPlan,
) -> tuple[list[dict[str, typing.Any]], list[dict[str, str]]]:
    """Build node and link payloads for a compiled execution plan."""
    stage_by_invocation = {
        invocation.id: stage_number
        for stage_number, stage in enumerate(plan.execution_stages, start=1)
        for invocation in stage
    }
    nodes = [
        {
            "id": invocation.id,
            "node_type": "invocation",
            "function_kind": invocation.function_kind,
            "stage": stage_by_invocation[invocation.id],
            "label": invocation_label(invocation),
            "label_lines": invocation_label_lines(invocation),
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
    links = [
        {"source": dependency_id, "target": invocation.id}
        for invocation in plan.invocations
        for dependency_id in invocation.dependency_ids
    ]
    return nodes, links
