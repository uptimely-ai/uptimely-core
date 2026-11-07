"""Emit portable execution-plan invocations from compiler graph nodes."""

from __future__ import annotations

from uptimely import plan as execution_plan
from uptimely import spec

from . import graph as invocation_graph


def emit_invocation(
    spec_definition: spec.Spec,
    graph: invocation_graph.InvocationGraph,
    node: invocation_graph.InvocationNode,
) -> execution_plan.Invocation:
    """Create one portable invocation, resolving its arguments and dependencies."""
    function = spec_definition.functions.get(node.function_id)
    if function is None or not function.entrypoint:
        raise ValueError(
            f"Missing entrypoint for function {node.function_id} "
            f"used by operator {node.operator_id}"
        )
    profile_key = spec_definition.profile_keys[node.dataset_id]
    id_columns = spec_definition.grain_keys_by_profile[profile_key]
    arguments = graph.operator_for(node).resolve_args(
        function_id=node.function_id,
        function_kind=function.kind,
        profile_id=node.dataset_id,
        grain_keys_by_profile=spec_definition.grain_keys_by_profile,
        resources=spec_definition.binding_resources,
        id_columns=id_columns,
    )
    profile = spec_definition.profiles[node.dataset_id]
    column_types = {
        feature_id: feature.type
        for feature_id, feature in profile.features.items()
        if feature.type is not None
    } | spec_definition.grain_key_types_by_profile[profile_key]
    return execution_plan.Invocation(
        id=node.node_id,
        function_kind=function.kind,
        entrypoint=function.entrypoint,
        function_id=node.function_id,
        operator_id=node.operator_id,
        dataset_id=node.dataset_id,
        output_features=list(node.output_features),
        input_features=list(node.input_features),
        arguments=arguments,
        dependency_ids=[dependency.node_id for dependency in graph.dependencies(node)],
        row_context=node.row_context,
        id_columns=list(id_columns),
        column_types=column_types,
        argument_types={key: argument.type for key, argument in function.args.items()},
    )
