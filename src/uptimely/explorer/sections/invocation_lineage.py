"""Prepare invocation-lineage payloads for compiled execution plans."""

import typing

from uptimely import plan as execution_plan
from uptimely import spec
from uptimely.explorer import common
from uptimely.spec import function_kinds as functions
from uptimely.spec.model import base


def invocation_lineage_payload(
    plan: execution_plan.ExecutionPlan,
    spec_definition: spec.Spec,
    feature_labels: typing.Mapping[str, str] | None = None,
) -> tuple[list[dict[str, typing.Any]], list[dict[str, str]]]:
    """Build invocation nodes and links for a compiled plan.

    Args:
        plan: Compiled invocations and dependency stages.
        spec_definition: Declarations used to resolve display metadata.
        feature_labels: Optional prebuilt feature-label index shared with plan cards.

    Returns:
        Invocation nodes and directed dependency links.
    """
    if spec_definition is None:
        raise ValueError("spec_definition is required to prepare invocation lineage")
    stage_by_invocation = {
        invocation_id: stage_number
        for stage_number, stage in enumerate(plan.stages, start=1)
        for invocation_id in stage
    }
    if feature_labels is None:
        feature_labels = common.feature_labels(spec_definition)
    nodes: list[dict[str, typing.Any]] = []
    invocations_by_id = plan.invocations_by_id
    for invocation in sorted(plan.invocations, key=lambda item: item.id):
        function = spec_definition.functions[invocation.function_id]
        kind = functions.FUNCTION_KINDS[invocation.function_kind]
        is_merge = invocation.function_kind == functions.MERGE
        dataset = (
            spec_definition.profiles.get(invocation.dataset_id) if invocation.dataset_id else None
        )
        function_name = function.name or invocation.function_id
        dataset_name = dataset.name or dataset.id if dataset is not None else invocation.dataset_id
        nodes.append(
            {
                "id": invocation.id,
                "node_type": "invocation",
                "function_kind": invocation.function_kind,
                "phase": "merge" if is_merge else "compute",
                "is_effect": kind.is_effect,
                "stage": stage_by_invocation[invocation.id],
                "label": function_name,
                "label_lines": [function_name],
                "function_id": invocation.function_id,
                "function_name": function_name,
                "arguments": invocation.arguments,
                "merge_target": invocation.arguments.get("target") if is_merge else None,
                "fragment_source": invocation.arguments.get("fragment") if is_merge else None,
                "merge_keys": invocation.arguments.get("target_keys") if is_merge else None,
                "operator_id": invocation.operator_id,
                "operator_name": base.humanize_identifier(invocation.operator_id),
                "profile": invocation.dataset_id,
                "dataset_id": invocation.dataset_id,
                "dataset_name": dataset_name,
                "feature": (
                    ", ".join(
                        feature_labels.get(feature, feature)
                        for feature in invocation.output_features
                    )
                    if kind.is_effect or kind.is_transformer
                    else None
                ),
                "input_features": invocation.input_features,
                "output_features": invocation.output_features,
                "dependency_ids": sorted(invocation.dependency_ids),
            }
        )
    links = []
    for invocation in plan.invocations:
        for dependency_id in invocation.dependency_ids:
            dependency = invocations_by_id[dependency_id]
            dependency_type = (
                "fragment"
                if invocation.function_kind == functions.MERGE
                and dependency.operator_id == invocation.operator_id
                and dependency.dataset_id == invocation.dataset_id
                else "feature"
            )
            links.append(
                {
                    "source": dependency_id,
                    "target": invocation.id,
                    "dependency_type": dependency_type,
                }
            )
    return nodes, links
