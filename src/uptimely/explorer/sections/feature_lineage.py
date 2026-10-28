"""Prepare and render feature lineage for the Explorer website."""

import dataclasses
import json
import typing

from graphable import views

from uptimely.explorer import common, graph_style, render
from uptimely.spec.feature_graph import models

if typing.TYPE_CHECKING:
    from uptimely.spec.feature_graph.feature_graph import FeatureGraphBase

SECTION = render.WebsiteSection(
    active_page="spec",
    pages=(
        render.WebsitePage(
            "graph/feature_lineage.html.j2",
            render.WEBSITE_PAGES["spec"]["feature_lineage"],
            active_section="feature_lineage",
        ),
    ),
)
__all__ = ["SECTION", "build_context", "feature_lineage_payload"]


def feature_lineage_payload(
    feature_graph: "FeatureGraphBase",
) -> tuple[list[dict[str, typing.Any]], list[dict[str, str]]]:
    """Build node and link payloads for feature lineage."""
    config = views.CytoscapeStylingConfig(
        node_data_fnc=lambda node: _node_render_data(node.reference),
        reference_fnc=lambda node: node.reference.node_id,
    )
    elements = json.loads(views.create_topology_cytoscape(feature_graph.graph, config))

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
    feature_graph: "FeatureGraphBase",
) -> dict[str, object]:
    """Prepare feature-lineage payload and style data without rendering or writing pages.

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
