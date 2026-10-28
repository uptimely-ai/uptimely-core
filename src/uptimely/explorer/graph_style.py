"""Shared visual settings for Explorer graph sections."""

import dataclasses

from uptimely.spec import functions


@dataclasses.dataclass
class GraphStyle:
    """Visual appearance settings shared by feature and invocation lineage views."""

    function_color: str = "#b9c9d8"
    input_color: str = "#64c7a8"
    feature_color: str = "#6ebcf4"
    function_colors: dict[str, str] = dataclasses.field(
        default_factory=lambda: {
            functions.READ: "#4c78a8",
            functions.ESCAPE: "#a78bfa",
            functions.VECTORIZE: "#f58518",
            functions.COLLAPSE: "#e45756",
            functions.CONFORM: "#72b7b2",
            functions.EXPAND: "#b279a2",
            functions.WRITE: "#ff9da6",
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
