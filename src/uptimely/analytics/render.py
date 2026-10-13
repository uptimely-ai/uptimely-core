"""HTML templates for interactive dependency graphs."""

import dataclasses
import json
import pathlib
import typing

from graphable import views

from uptimely import render

if typing.TYPE_CHECKING:
    from . import feature_graph


@dataclasses.dataclass
class GraphStyle:
    """Visual appearance settings for the dependency graph."""

    function_color: str = "#d62828"
    input_color: str = "#64c7a8"
    feature_color: str = "#6ebcf4"
    function_colors: dict[str, str] = dataclasses.field(
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


def _render_graph_html(
    nodes: list[dict[str, typing.Any]],
    links: list[dict[str, str]],
    style: GraphStyle | None = None,
    *,
    dimension: typing.Literal["2d", "3d"],
) -> str:
    """Render the dependency graph as interactive 2D or 3D HTML.

    Args:
        nodes: Graph nodes with stable identifiers and display metadata.
        links: Directed connections between node identifiers.
        style: Optional graph appearance settings.
        dimension: Graph layout to render.

    Returns:
        The complete HTML document.

    Raises:
        ValueError: If the requested graph dimension is not supported.
    """
    if dimension not in ("2d", "3d"):
        raise ValueError(f"Unsupported graph dimension: {dimension!r}. Choose '2d' or '3d'.")

    style = style or GraphStyle()
    environment = render.html_environment()
    graph_data = json.dumps(
        {
            "nodes": sorted(nodes, key=lambda node: node["id"]),
            "links": sorted(links, key=lambda link: (link["source"], link["target"])),
        }
    ).replace("</script>", r"<\/script>")
    template = environment.get_template(f"graph/feature_graph_{dimension}.html.j2")
    return template.render(
        style=style,
        dimension=dimension,
        graph_data=graph_data,
        include_navigation=True,
        active_page="graph",
        active_section=dimension,
        root_path=root_path,
    )


def graph_payload_from_cytoscape(
    graph: "feature_graph.GraphBase",
) -> tuple[list[dict[str, typing.Any]], list[dict[str, str]]]:
    """Normalize Cytoscape graph elements into node and link payloads."""
    config = views.CytoscapeStylingConfig(
        node_data_fnc=lambda node: graph._node_data(node.reference),
        reference_fnc=lambda node: graph._node_key(node.reference),
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


def _create_website_pages(
    graph: "feature_graph.GraphBase",
    output_directory: pathlib.Path,
) -> None:
    """Write both feature graph views within the documentation website.

    Args:
        graph: The feature dependency graph to export.
        output_directory: Directory shared by all website pages.
    """
    output_directory.mkdir(parents=True, exist_ok=True)
    nodes, links = graph_payload_from_cytoscape(graph)
    for dimension in ("2d", "3d"):
        document = _render_graph_html(nodes, links, dimension=dimension)
        target = output_directory / f"feature_graph_{dimension}.html"
        target.write_text(document, encoding="utf-8")
