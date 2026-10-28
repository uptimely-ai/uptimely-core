"""Emit portable execution-plan invocations from compiler graph nodes."""

from __future__ import annotations

from uptimely import execution_plan, spec
from uptimely.spec import binding_resolution

from . import graph as invocation_graph


def emit_invocations(
    spec_definition: spec.Spec,
    graph: invocation_graph.InvocationGraph,
) -> list[execution_plan.Invocation]:
    """Create portable invocations for all nodes in a selected graph."""
    return [emit_invocation(spec_definition, graph, node) for node in graph.invocations]


def emit_invocation(
    spec_definition: spec.Spec,
    graph: invocation_graph.InvocationGraph,
    node: invocation_graph.InvocationNode,
) -> execution_plan.Invocation:
    """Create one portable invocation, resolving its arguments and dependencies."""
    function = spec_definition.functions.get(node.function_id)
    if function is None or not function.entrypoint:
        raise ValueError(
            f"Missing entrypoint for function {node.function_id} used by mapping {node.mapping_id}"
        )
    arguments = binding_resolution.resolve_binding_args(
        node.arguments,
        node.dataset_id,
        node.feature_id,
        spec_definition.dimension_ids_by_dataset,
    )
    return execution_plan.Invocation(
        id=node.node_id,
        operation=function.kind,
        entrypoint=function.entrypoint,
        function_id=node.function_id,
        mapping_id=node.mapping_id,
        entity_id=node.entity_id,
        dataset_id=node.dataset_id,
        output_features=list(node.output_features),
        input_features=list(node.input_features),
        arguments=arguments,
        dependency_ids=[dependency.node_id for dependency in graph.dependencies(node)],
        row_context=node.row_context,
    )
