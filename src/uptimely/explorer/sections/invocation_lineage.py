"""Prepare invocation-lineage payloads for compiled execution plans."""

import typing

from uptimely import execution_plan, spec
from uptimely.spec import functions


def invocation_lineage_payload(
    plan: execution_plan.ExecutionPlan,
    spec_definition: spec.Spec,
) -> tuple[list[dict[str, typing.Any]], list[dict[str, str]]]:
    """Build invocation and dependency link payloads for a compiled plan."""
    if spec_definition is None:
        raise ValueError("spec_definition is required to render invocation lineage")
    stage_by_invocation = {
        invocation.id: stage_number
        for stage_number, stage in enumerate(plan.execution_stages, start=1)
        for invocation in stage
    }
    feature_labels = {
        feature_id: feature.name or feature_id
        for entity in spec_definition.entities.values()
        for dataset in entity.datasets.values()
        for feature_id, feature in dataset.features.items()
    }
    feature_labels.update(
        {
            dimension_id: dimension.name or dimension_id
            for dimension_id, dimension in spec_definition.dimensions.items()
        }
    )
    nodes = []
    for invocation in sorted(plan.invocations, key=lambda item: item.id):
        function = spec_definition.functions[invocation.function_id]
        entity = spec_definition.entities[invocation.entity_id]
        dataset = entity.datasets.get(invocation.dataset_id) if invocation.dataset_id else None
        function_name = function.name or invocation.function_id
        dataset_name = (
            dataset.name or invocation.dataset_id if dataset is not None else invocation.dataset_id
        )
        nodes.append(
            {
                "id": invocation.id,
                "node_type": "invocation",
                "function_kind": invocation.function_kind,
                "stage": stage_by_invocation[invocation.id],
                "label": function_name,
                "label_lines": [function_name],
                "function_id": invocation.function_id,
                "function_name": function_name,
                "arguments": invocation.arguments,
                "mapping_id": invocation.mapping_id,
                "entity": invocation.entity_id,
                "dataset_id": invocation.dataset_id,
                "dataset_name": dataset_name,
                "feature": (
                    ", ".join(
                        feature_labels.get(feature, feature)
                        for feature in invocation.output_features
                    )
                    if invocation.function_kind in {functions.ESCAPE, functions.VECTORIZE}
                    else None
                ),
                "input_features": invocation.input_features,
                "output_features": invocation.output_features,
                "dependency_ids": sorted(invocation.dependency_ids),
            }
        )
    links = [
        {"source": dependency_id, "target": invocation.id}
        for invocation in plan.invocations
        for dependency_id in invocation.dependency_ids
    ]
    return nodes, links
