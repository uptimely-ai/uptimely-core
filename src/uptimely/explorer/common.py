"""Shared helpers for Explorer sections."""

import json
import typing

from uptimely import spec


def feature_labels(spec_definition: spec.Spec) -> dict[str, str]:
    """Index feature display names, with global dimensions taking precedence."""
    labels = {
        feature.id: feature.name or feature.id for feature in spec_definition.features.values()
    }
    labels.update(
        (resolution.key, dimension.name or resolution.key)
        for dimension in spec_definition.dimensions.values()
        for resolution in dimension.resolutions.values()
    )
    return labels


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


def filled_fields(**fields: object) -> dict[str, typing.Any]:
    """Return display metadata without null-valued optional fields."""
    return {name: value for name, value in fields.items() if value is not None}
