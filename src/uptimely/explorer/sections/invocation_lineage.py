"""Prepare invocation-lineage payloads for compiled execution plans."""

import typing

from uptimely import compiler, spec
from uptimely import plan as plan_module
from uptimely.explorer import common
from uptimely.spec.model import base


def invocation_lineage_payload(
    plan: plan_module.ExecutionPlan,
    spec_definition: spec.Spec,
    feature_labels: typing.Mapping[str, str] | None = None,
) -> tuple[list[dict[str, typing.Any]], list[dict[str, str]]]:
    """Build invocation nodes and links for a compiled plan.

    Args:
        plan: Compiled invocations and ordered stages.
        spec_definition: Declarations used to resolve display metadata.
        feature_labels: Optional prebuilt feature-label index shared with plan cards.

    Returns:
        Invocation nodes and compiler dependency links.
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
    graph = compiler.Compiler.invocation_graph(spec_definition)
    graph_nodes = {
        (
            node.semantics.profile_id,
            node.semantics.operator_id,
            node.semantics.role,
            node.semantics.function_id,
        ): node
        for node in graph.invocations
    }
    invocations_by_key = {}
    for invocation in plan.invocations:
        semantics = invocation.semantics
        if semantics is None:
            raise ValueError(f"Invocation {invocation.id} requires semantics for topology")
        key = (semantics.profile_id, semantics.operator_id, semantics.role, semantics.function_id)
        if key not in graph_nodes:
            raise ValueError(f"Invocation {invocation.id} does not match a Spec binding")
        if key in invocations_by_key:
            raise ValueError(f"Multiple invocations match the same Spec binding: {key}")
        invocations_by_key[key] = invocation
    plan_ids = {
        graph_nodes[key].node_id: invocation.id for key, invocation in invocations_by_key.items()
    }
    dependencies = {
        invocation.id: [
            plan_ids[dependency.node_id]
            for dependency in graph.dependencies(graph_nodes[key])
            if dependency.node_id in plan_ids
        ]
        for key, invocation in invocations_by_key.items()
    }
    nodes: list[dict[str, typing.Any]] = []
    invocations_by_id = plan.invocations_by_id
    for invocation in sorted(plan.invocations, key=lambda item: item.id):
        function = spec_definition.functions[invocation.semantics.function_id]
        is_merge = invocation.semantics.role == "merge"
        key = (invocation.semantics.profile_id, invocation.semantics.operator_id)
        operator = spec_definition.operators_by_key[key]
        grain_relationships = [
            {
                "source_profile": (
                    spec_definition.profiles_by_key[source].id if source is not None else None
                ),
                "relationship": relationship,
            }
            for source, relationship in operator.grain_relationships(spec_definition, key).items()
        ]
        profile = (
            spec_definition.profiles.get(invocation.semantics.profile_id)
            if invocation.semantics.profile_id
            else None
        )
        function_name = function.name or invocation.semantics.function_id
        profile_name = (
            profile.name or profile.id if profile is not None else invocation.semantics.profile_id
        )
        nodes.append(
            {
                "id": invocation.id,
                "node_type": "invocation",
                "execution_form": operator.execution_form,
                "binding_roles": list(operator.binding_roles),
                "grain_relationships": grain_relationships,
                "function_returns": function.returns,
                "role": invocation.semantics.role,
                "result": invocation.semantics.result,
                "stage": stage_by_invocation[invocation.id],
                "label": function_name,
                "label_lines": [function_name],
                "function_id": invocation.semantics.function_id,
                "function_name": function_name,
                "arguments": invocation.arguments,
                "merge_dataset": invocation.arguments.get("dataset") if is_merge else None,
                "fragment_source": invocation.arguments.get("fragment") if is_merge else None,
                "merge_keys": invocation.arguments.get("dataset_identifiers") if is_merge else None,
                "operator_id": invocation.semantics.operator_id,
                "operator_name": base.humanize_identifier(invocation.semantics.operator_id),
                "profile": invocation.semantics.profile_id,
                "profile_id": invocation.semantics.profile_id,
                "profile_name": profile_name,
                "feature": (
                    ", ".join(
                        feature_labels.get(feature, feature)
                        for feature in invocation.semantics.output_features
                    )
                    if invocation.semantics.output_features
                    else None
                ),
                "input_features": invocation.semantics.input_features,
                "output_features": invocation.semantics.output_features,
                "dependency_ids": sorted(dependencies[invocation.id]),
            }
        )
    links = []
    for invocation in plan.invocations:
        for dependency_id in dependencies[invocation.id]:
            dependency = invocations_by_id[dependency_id]
            dependency_type = (
                "fragment"
                if dependency.returns is not None
                and dependency.returns.startswith(plan_module.Variable.FRAGMENT)
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
