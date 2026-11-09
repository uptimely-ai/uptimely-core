"""Prepare invocation-lineage payloads for compiled execution plans."""

import typing

from uptimely import plan as plan_module
from uptimely import spec
from uptimely.explorer import common
from uptimely.spec.model import base


def invocation_lineage_payload(
    plan: plan_module.ExecutionPlan,
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
        is_merge = invocation.role == "merge"
        key = (invocation.profile_id, invocation.operator_id)
        grain_relationships = [
            {
                "source_profile": (
                    spec_definition.profiles_by_key[source].id if source is not None else None
                ),
                "relationship": relationship,
            }
            for source, relationship in spec_definition.operator_grain_relationships[key].items()
        ]
        profile = (
            spec_definition.profiles.get(invocation.profile_id) if invocation.profile_id else None
        )
        function_name = function.name or invocation.function_id
        profile_name = profile.name or profile.id if profile is not None else invocation.profile_id
        nodes.append(
            {
                "id": invocation.id,
                "node_type": "invocation",
                "operator_label": spec_definition.operator_kinds[key],
                "execution_form": spec_definition.operator_execution_forms[key],
                "binding_roles": list(spec_definition.operator_binding_roles[key]),
                "grain_relationships": grain_relationships,
                "function_returns": function.returns,
                "role": invocation.role,
                "result": invocation.result,
                "stage": stage_by_invocation[invocation.id],
                "label": function_name,
                "label_lines": [function_name],
                "function_id": invocation.function_id,
                "function_name": function_name,
                "arguments": invocation.arguments,
                "merge_dataset": invocation.arguments.get("dataset") if is_merge else None,
                "fragment_source": invocation.arguments.get("fragment") if is_merge else None,
                "merge_keys": invocation.arguments.get("dataset_keys") if is_merge else None,
                "operator_id": invocation.operator_id,
                "operator_name": base.humanize_identifier(invocation.operator_id),
                "profile": invocation.profile_id,
                "profile_id": invocation.profile_id,
                "profile_name": profile_name,
                "feature": (
                    ", ".join(
                        feature_labels.get(feature, feature)
                        for feature in invocation.output_features
                    )
                    if invocation.output_features
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
                if invocation.role == "merge"
                and dependency.operator_id == invocation.operator_id
                and dependency.profile_id == invocation.profile_id
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
