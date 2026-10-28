"""Prepare invocation-lineage payloads for compiled execution plans."""

import typing

from uptimely import execution_plan
from uptimely.spec import functions


def invocation_lineage_payload(
    plan: execution_plan.ExecutionPlan,
) -> tuple[list[dict[str, typing.Any]], list[dict[str, str]]]:
    """Build invocation and dependency link payloads for a compiled plan."""
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
            "label": invocation.function_id,
            "label_lines": [invocation.function_id],
            "function_id": invocation.function_id,
            "arguments": invocation.arguments,
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
