"""Render feature dependency graphs for the explorer website."""

import dataclasses
import json
import pathlib
import typing

from graphable import views

from uptimely import project
from uptimely.spec import operations

from . import render

if typing.TYPE_CHECKING:
    from uptimely.spec.feature_graph.graph import GraphBase


@dataclasses.dataclass
class GraphStyle:
    """Visual appearance settings for the dependency graph."""

    function_color: str = "#b9c9d8"
    input_color: str = "#64c7a8"
    feature_color: str = "#6ebcf4"
    function_colors: dict[str, str] = dataclasses.field(
        default_factory=lambda: {
            operations.READ: "#4c78a8",
            operations.ESCAPE: "#a78bfa",
            operations.VECTORIZE: "#f58518",
            operations.COLLAPSE: "#e45756",
            operations.CONFORM: "#72b7b2",
            operations.EXPAND: "#b279a2",
            operations.WRITE: "#ff9da6",
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
    index_filename: str = project.EXPLORER_INDEX_FILE.name,
    project_name: str | None = None,
    execution_scope: str = "all features",
    is_scoped: bool = False,
) -> str:
    """Render one feature graph page with selectable 2D and 3D views.

    Args:
        nodes: Graph nodes with stable identifiers and display metadata.
        links: Directed connections between node identifiers.
        style: Optional graph appearance settings.
        index_filename: Filename of the website dashboard.
        project_name: Project title displayed in the shared top bar.
        execution_scope: Feature coverage of the rendered build.
        is_scoped: Whether the plan covers a selected feature subset.

    Returns:
        The complete HTML document.
    """
    style = style or GraphStyle()
    environment = render.html_environment()
    graph_data = json.dumps(
        {
            "nodes": sorted(nodes, key=lambda node: node["id"]),
            "links": sorted(links, key=lambda link: (link["source"], link["target"])),
        }
    ).replace("</script>", r"<\/script>")
    template = environment.get_template("graph/feature_graph.html.j2")
    return template.render(
        style=style,
        graph_style_data=dataclasses.asdict(style),
        graph_data=graph_data,
        include_navigation=True,
        active_page="graph",
        index_filename=index_filename,
        project_name=project_name,
        root_path="../",
        execution_scope=execution_scope,
        is_scoped=is_scoped,
    )


def graph_payload_from_cytoscape(
    graph: "GraphBase",
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
    graph: "GraphBase",
    output_directory: pathlib.Path,
    *,
    index_filename: str = project.EXPLORER_INDEX_FILE.name,
    project_name: str | None = None,
    execution_scope: str = "all features",
    is_scoped: bool = False,
) -> None:
    """Write the unified feature graph page within the documentation website.

    Args:
        graph: The feature dependency graph to export.
        output_directory: Directory shared by all website pages.
        index_filename: Filename of the website dashboard.
        project_name: Project title displayed in the shared top bar.
        execution_scope: Feature coverage of the rendered build.
        is_scoped: Whether the plan covers a selected feature subset.
    """
    target = output_directory / render.WEBSITE_PAGES["graph"]["lineage"]
    target.parent.mkdir(parents=True, exist_ok=True)
    nodes, links = graph_payload_from_cytoscape(graph)
    document = _render_graph_html(
        nodes,
        links,
        index_filename=index_filename,
        project_name=project_name,
        execution_scope=execution_scope,
        is_scoped=is_scoped,
    )
    target.write_text(document, encoding="utf-8")
