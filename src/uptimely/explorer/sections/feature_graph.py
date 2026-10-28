"""Prepare and render feature dependency graphs for the Explorer website."""

import dataclasses
import json
import typing

from graphable import views

from uptimely.explorer import common, graph_style, render
from uptimely.spec.feature_graph import models

if typing.TYPE_CHECKING:
    from uptimely.spec.feature_graph.graph import GraphBase

SECTION = render.WebsiteSection(
    active_page="graph",
    pages=(
        render.WebsitePage("graph/feature_graph.html.j2", render.WEBSITE_PAGES["graph"]["lineage"]),
    ),
)
__all__ = ["SECTION", "build_context", "feature_graph_payload"]


def feature_graph_payload(
    graph: "GraphBase",
) -> tuple[list[dict[str, typing.Any]], list[dict[str, str]]]:
    """Build node and link payloads for a feature dependency graph."""
    config = views.CytoscapeStylingConfig(
        node_data_fnc=lambda node: _node_render_data(node.reference),
        reference_fnc=lambda node: node.reference.node_id,
    )
    elements = json.loads(views.create_topology_cytoscape(graph.graph, config))

    nodes: list[dict[str, typing.Any]] = []
    links: list[dict[str, str]] = []

    for element in elements:
        data = element.get("data", {})
        if "source" in data:
            links.append(
                {
                    "source": str(data["source"]),
                    "target": str(data["target"]),
                }
            )
            continue
        nodes.append(data)

    return nodes, links


def _node_render_data(
    reference: models.FeatureNode | models.FunctionNode,
) -> dict[str, object]:
    """Build Explorer display metadata from a feature graph node."""
    if isinstance(reference, models.FunctionNode):
        return render.filled_fields(
            node_type="feature",
            is_function=True,
            label=(
                f"{reference.name} · {reference.action_id}"
                if reference.action_id is not None
                else reference.name
            ),
            action_id=reference.action_id,
            features=list(reference.features),
            entity=reference.entity,
            function_kind=(reference.function.kind if reference.function is not None else None),
            type="python_function" if reference.function is not None else None,
            entrypoint=(reference.function.entrypoint if reference.function is not None else None),
            info=(
                {"description": reference.function.description}
                if reference.function is not None
                else None
            ),
        )

    return render.filled_fields(
        node_type="feature",
        is_function=False,
        label=reference.name,
        entity=reference.entity,
        data_type=reference.data_type,
    )


def build_context(
    graph: "GraphBase",
) -> dict[str, object]:
    """Prepare graph payload and style data without rendering or writing pages.

    Args:
        graph: The feature dependency graph to display.

    Returns:
        Serialized feature graph and shared visual style.
    """
    nodes, links = feature_graph_payload(graph)
    style = graph_style.GraphStyle()
    return {
        "style": style,
        "graph_style_data": dataclasses.asdict(style),
        "graph_data": common.serialize_graph_payload(nodes, links),
    }
