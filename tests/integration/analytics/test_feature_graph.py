from pathlib import Path

import pytest

from uptimely.analytics import FeatureGraph
from uptimely.analytics.models import FeatureNode, FunctionNode
from uptimely.spec import Specification

SPEC_PATH = Path("examples/example_1/generated/spec/spec.json")


def test_system_graph_connects_functions_to_feature_outputs() -> None:
    specification = Specification.from_json(SPEC_PATH)
    system = FeatureGraph(specification)

    function_nodes = {function.id: function for function in system.functions}
    assert "aggregate_by_dimension" in function_nodes
    assert "normalize_health_signal" in function_nodes
    assert "extract_recommendation_value" in function_nodes

    actual_edges = {
        (
            source.reference.name,
            neighbor_node.reference.name,
        )
        for source in system.graph
        if isinstance(source.reference, FunctionNode)
        for neighbor_node, _attrs in system.graph.neighbors(source)
        if isinstance(neighbor_node.reference, FeatureNode)
    }

    assert ("aggregate_by_dimension", "bearing_temperature_max") in actual_edges
    assert ("normalize_health_signal", "health_signal_normalized") in actual_edges
    assert ("extract_recommendation_value", "recommended_flow_rate") in actual_edges


def test_system_graph_contains_function_nodes() -> None:
    specification = Specification.from_json(SPEC_PATH)
    non_analytics = specification.resolved_functions[0].model_copy(
        update={"id": "non_analytics_function", "role": "serving"}
    )
    specification.resolved_functions.append(non_analytics)
    system = FeatureGraph(specification)

    function_nodes = [
        node.reference for node in system.graph if isinstance(node.reference, FunctionNode)
    ]
    analytics_function_ids = {function.id for function in system.functions}

    assert function_nodes
    assert any(function.name == "aggregate_by_dimension" for function in function_nodes)
    assert all(function.name in analytics_function_ids for function in function_nodes)
    assert all(function.name != "non_analytics_function" for function in function_nodes)
    assert "bearing_temperature" in system.input_names
    assert all(isinstance(name, str) for name in system.input_names)

    graph_text = system.print_graph()
    assert "Function(" not in graph_text
    assert "aggregate_by_dimension" in graph_text


def test_subset_raises_helpful_error_for_missing_output() -> None:
    specification = Specification.from_json(SPEC_PATH)
    system = FeatureGraph(specification)

    with pytest.raises(ValueError, match=r"Unknown output feature\(s\): temperature_3"):
        system.subset(["temperature_3"])


def test_system_graph_builds_from_entity_feature_bindings() -> None:
    specification = Specification.from_json(SPEC_PATH)
    system = FeatureGraph(specification)

    assert "bearing_temperature_max" in system.feature_names
    assert "health_signal_normalized" in system.feature_names


def test_system_graph_can_export_html(tmp_path: Path) -> None:
    specification = Specification.from_json(SPEC_PATH)
    system = FeatureGraph(specification)

    output = tmp_path / "graph.html"
    saved = system.export_html(output)
    html = output.read_text(encoding="utf-8")

    assert saved == output
    assert output.exists()
    assert "3d-force-graph" in html
    assert "SphereGeometry" in html
    assert "ConeGeometry" not in html
    assert "OctahedronGeometry" in html
    assert "CylinderGeometry" not in html
    assert (
        "${node.is_function ? 'function' : 'feature'}: ${node.label}"
        "<br>entity: ${node.entity || 'n/a'}" in html
    )
    assert "entity: ${node.entity || 'n/a'}" in html
    assert "<strong>Entity:</strong>" in html
    assert '"node_type": "feature"' in html
    assert '"is_function": true' in html
    assert '"is_function": false' in html
    assert "<strong>Node type:</strong> Function" in html
    assert "<strong>Function:</strong> ${label}" in html
    assert "<strong>Produces:</strong> ${formatDetailValue(feature)}" in html
    assert "Feature</span>" in html
    assert "Read</span>" in html
    assert "Vectorize</span>" in html
    assert "Collapse</span>" in html
    assert "Conform</span>" in html
    assert "Expand</span>" in html
    assert "Write</span>" in html
    assert "input_color" not in html

    subset_output = tmp_path / "subset.html"
    system.subset(["health_signal_normalized"]).export_html(subset_output)
    subset_html = subset_output.read_text(encoding="utf-8")
    assert '"node_type": "feature"' in subset_html
