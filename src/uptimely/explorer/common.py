"""Shared helpers for Explorer sections."""

import json
import typing


def serialize_graph_payload(
    nodes: list[dict[str, typing.Any]],
    links: list[dict[str, str]],
) -> str:
    """Serialize a graph payload with stable ordering and script-safe JSON."""
    return json.dumps(
        {
            "nodes": sorted(nodes, key=lambda node: node["id"]),
            "links": sorted(links, key=lambda link: (link["source"], link["target"])),
        }
    ).replace("</script>", r"<\/script>")
