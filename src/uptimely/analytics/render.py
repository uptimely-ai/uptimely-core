"""HTML templates for interactive dependency graphs."""

import json
import typing
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from graphable.views import CytoscapeStylingConfig, create_topology_cytoscape
from jinja2 import Environment, PackageLoader, select_autoescape

if typing.TYPE_CHECKING:
    from .feature_graph import GraphBase


@dataclass
class GraphStyle:
    """Visual appearance settings for the 3D dependency graph."""

    function_color: str = "#d62828"
    input_color: str = "#64c7a8"
    feature_color: str = "#6ebcf4"
    function_colors: dict[str, str] = field(
        default_factory=lambda: {
            "read": "#4c78a8",
            "vectorize": "#f58518",
            "collapse": "#e45756",
            "conform": "#72b7b2",
            "expand": "#b279a2",
            "write": "#ff9da6",
        }
    )
    background_color: str = "#101820"
    link_color: str = "#8fa3b5"
    label_color: str = "#d2f4f0"
    function_node_size: float = 12
    feature_node_size: float = 5
    node_rel_size: float = 5
    node_resolution: int = 12
    link_width: float = 0.5
    link_opacity: float = 0.9
    arrow_length: float = 4
    arrow_rel_pos: float = 1
    charge_strength: float = -75
    charge_distance_max: float = 110
    link_distance: float = 30


def render_graph_html(
    nodes: list[dict[str, typing.Any]],
    links: list[dict[str, str]],
    style: GraphStyle | None = None,
) -> str:
    """Render the dependency graph as an interactive 3D HTML."""
    style = style or GraphStyle()
    environment = Environment(
        loader=PackageLoader("uptimely", "analytics/templates"),
        autoescape=select_autoescape(["html"]),
    )
    graph_data = json.dumps({"nodes": nodes, "links": links}).replace("</script>", r"<\/script>")
    template = environment.get_template("graph.html.j2")
    return template.render(
        style=style,
        graph_data=graph_data,
        generated_at=datetime.now().astimezone().isoformat(timespec="seconds"),
    )


def graph_payload_from_cytoscape(
    graph: "GraphBase",
) -> tuple[list[dict[str, typing.Any]], list[dict[str, str]]]:
    """Normalize Cytoscape graph elements into node and link payloads."""
    config = CytoscapeStylingConfig(
        node_data_fnc=lambda node: graph._node_data(node.reference),
        reference_fnc=lambda node: graph._node_key(node.reference),
    )
    elements = json.loads(create_topology_cytoscape(graph.graph, config))

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


def export_graph_html(
    graph: "GraphBase", output_path: str | Path, style: GraphStyle | None = None
) -> Path:
    """Export a feature dependency graph as an interactive 3D HTML document."""
    target = Path(output_path)
    if target.suffix.lower() != ".html":
        target = target.with_suffix(".html")
    target.parent.mkdir(parents=True, exist_ok=True)

    nodes, links = graph_payload_from_cytoscape(graph)

    document = render_graph_html(nodes, links, style)
    target.write_text(document, encoding="utf-8")
    return target
