"""Prepare feature lineage data for the Explorer."""

import dataclasses
import typing

from uptimely.explorer import common, graph_style
from uptimely.spec import function_kinds as functions
from uptimely.spec.feature_graph import models

if typing.TYPE_CHECKING:
    from uptimely.spec.feature_graph import feature_graph as feature_graph_module

__all__ = ["build_context", "feature_lineage_payload"]


def feature_lineage_payload(
    feature_graph: "feature_graph_module.FeatureGraphBase",
) -> tuple[list[dict[str, typing.Any]], list[dict[str, str]]]:
    """Build node and link payloads for feature lineage."""
    ordered_nodes = feature_graph.graph.topological_order()
    nodes = [
        {
            "id": node.reference.node_id,
            "label": str(node.reference),
            "tags": list(node.tags),
            **_node_data(node.reference),
        }
        for node in ordered_nodes
    ]
    links = [
        {"source": node.reference.node_id, "target": dependent.reference.node_id}
        for node in ordered_nodes
        for dependent, _ in feature_graph.graph.internal_dependents(node)
    ]
    return nodes, links


def _node_data(
    reference: models.FeatureNode | models.OperatorNode,
) -> dict[str, object]:
    """Build Explorer metadata from a feature graph node."""
    if isinstance(reference, models.OperatorNode):
        return common.filled_fields(
            node_type="feature",
            is_operator=True,
            label=reference.function.name,
            operator_id=reference.operator_id,
            features=list(reference.features),
            profile=reference.profile_id,
            profile_id=reference.profile_id,
            profile_name=reference.profile_name,
            function_id=reference.function.id,
            function_name=reference.function.name,
            function_kind=reference.function.kind,
            is_effect=functions.FUNCTION_KINDS[reference.function.kind].is_effect,
            type="python_function",
            entrypoint=reference.function.entrypoint,
            info={"description": reference.function.description},
        )

    return common.filled_fields(
        node_type="feature",
        is_operator=False,
        label=reference.display_name or reference.name,
        feature_id=reference.name,
        profile=reference.profile_id,
        profile_id=reference.profile_id,
        profile_name=reference.profile_name,
        data_type=reference.data_type,
    )


def build_context(
    feature_graph: "feature_graph_module.FeatureGraphBase",
) -> dict[str, object]:
    """Prepare feature-lineage payload and style data without writing files.

    Args:
        feature_graph: The feature dependency graph to display.

    Returns:
        Serialized feature lineage and shared visual style.
    """
    nodes, links = feature_lineage_payload(feature_graph)
    style = graph_style.GraphStyle()
    return {
        "style": style,
        "graph_style_data": dataclasses.asdict(style),
        "graph_data": common.serialize_graph_payload(nodes, links),
    }
