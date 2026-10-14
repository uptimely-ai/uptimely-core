import pathlib
import sys

import pytest

from uptimely import analytics, spec
from uptimely.analytics import models
from uptimely.cli import cli
from uptimely.docs import docs

SPEC_PATH = pathlib.Path("examples/pump_analytics/_generated/spec/spec.json")


@pytest.mark.parametrize("verbose", [False, True])
def test_feature_graph_cli_inspects_without_exporting(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    verbose: bool,
) -> None:
    arguments = [
        "uptimely",
        "spec",
        "feature-graph",
        "--spec",
        str(SPEC_PATH.resolve()),
        "--features",
        "health_signal_normalized",
    ]
    if verbose:
        arguments.append("--verbose")
    monkeypatch.setattr(sys, "argv", arguments)
    monkeypatch.chdir(tmp_path)

    cli.main()

    output = capsys.readouterr().out
    assert "Feature graph:" in output
    assert "Selected feature subset: 2 features" in output
    assert ("Selected feature subset\n" in output) == verbose
    assert not list(tmp_path.iterdir())


def test_system_graph_connects_functions_to_feature_outputs() -> None:
    specification = spec.Specification.from_json(SPEC_PATH)
    system = analytics.FeatureGraph(specification)

    function_nodes = {function.id: function for function in system.functions}
    assert "maximum" in function_nodes
    assert "normalize_health_signal" in function_nodes
    assert "extract_recommendation_value" in function_nodes
    assert "extract_converged_flag" not in function_nodes
    assert "extract_convergence_flag" not in function_nodes
    recommendation_nodes = [
        node
        for node in system.graph
        if isinstance(node.reference, models.FunctionNode)
        and node.reference.name == "extract_recommendation_value"
    ]
    assert len(recommendation_nodes) == 1
    recommendation_outputs = {
        neighbor.reference.name
        for neighbor, _attrs in system.graph.neighbors(recommendation_nodes[0])
        if isinstance(neighbor.reference, models.FeatureNode)
    }
    assert recommendation_outputs == {
        "recommended_flow_rate",
        "recommended_discharge_pressure",
        "energy_cost_score",
        "converged",
    }
    assert set(recommendation_nodes[0].reference.features) == recommendation_outputs

    actual_edges = {
        (
            source.reference.name,
            neighbor_node.reference.name,
        )
        for source in system.graph
        if isinstance(source.reference, models.FunctionNode)
        for neighbor_node, _attrs in system.graph.neighbors(source)
        if isinstance(neighbor_node.reference, models.FeatureNode)
    }

    assert ("maximum", "bearing_temperature_max") in actual_edges
    assert ("normalize_health_signal", "health_signal_normalized") in actual_edges
    assert ("extract_recommendation_value", "recommended_flow_rate") in actual_edges
    assert ("extract_recommendation_value", "converged") in actual_edges


def test_system_graph_contains_function_nodes() -> None:
    specification = spec.Specification.from_json(SPEC_PATH)
    non_analytics = specification.resolved_functions[0].model_copy(
        update={"id": "non_analytics_function", "role": "serving"}
    )
    specification.resolved_functions.append(non_analytics)
    system = analytics.FeatureGraph(specification)

    function_nodes = [
        node.reference for node in system.graph if isinstance(node.reference, models.FunctionNode)
    ]
    analytics_function_ids = {function.id for function in system.functions}

    assert function_nodes
    assert any(function.name == "maximum" for function in function_nodes)
    assert all(function.name in analytics_function_ids for function in function_nodes)
    assert all(function.name != "non_analytics_function" for function in function_nodes)
    assert "bearing_temperature" in system.input_names
    assert all(isinstance(name, str) for name in system.input_names)

    graph_text = system.print_graph()
    assert "Function(" not in graph_text
    assert "maximum" in graph_text


def test_subset_raises_helpful_error_for_missing_output() -> None:
    specification = spec.Specification.from_json(SPEC_PATH)
    system = analytics.FeatureGraph(specification)

    with pytest.raises(ValueError, match=r"Unknown output feature\(s\): temperature_3"):
        system.subset(["temperature_3"])


def test_system_graph_builds_from_entity_feature_bindings() -> None:
    specification = spec.Specification.from_json(SPEC_PATH)
    system = analytics.FeatureGraph(specification)

    assert "bearing_temperature_max" in system.feature_names
    assert "health_signal_normalized" in system.feature_names


def test_dependency_features_keep_their_producer_entity_without_becoming_source_inputs() -> None:
    system = analytics.FeatureGraph(spec.Specification.from_json(SPEC_PATH))
    features = {
        node.reference.name: node.reference
        for node in system.graph
        if isinstance(node.reference, models.FeatureNode)
    }

    assert features["bearing_temperature_max"].entity == "pump"
    assert features["operating_point_recommendation"].entity == "pump_telemetry"
    assert features["bearing_temperature_max"].is_source_input is False
    assert features["operating_point_recommendation"].is_source_input is False


def test_website_includes_3d_lineage_html(tmp_path: pathlib.Path) -> None:
    specification = spec.Specification.from_json(SPEC_PATH)
    docs.Documentation(specification).create_html(tmp_path / "index.html")
    output = tmp_path / "spec/graph.html"
    html = output.read_text(encoding="utf-8")

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
    assert "<strong>Produces:</strong> ${formatDetailValue(features.join(', '))}" in html
    assert "Function</span>" in html
    for category in ("Read", "Vectorize", "Collapse", "Conform", "Expand", "Write"):
        assert f"{category} function</span>" not in html
    assert "entity-legend" in html
    assert "input_color" not in html


def test_website_includes_2d_lineage_html(tmp_path: pathlib.Path) -> None:
    specification = spec.Specification.from_json(SPEC_PATH)
    docs.Documentation(specification).create_html(tmp_path / "index.html")
    output = tmp_path / "spec/graph.html"
    html = output.read_text(encoding="utf-8")

    assert "force-graph@1.52.0/dist/force-graph.min.js" in html
    assert "ForceGraph()(graphContainer)" in html
    assert "graph-hint" not in html
    assert 'id="fit-graph"' in html
    assert "function prepareGraphLayout(graphData)" in html
    assert "function drawEntityLanes(ctx, globalScale)" not in html
    assert "function drawNode(node, ctx)" in html
    assert "function selectAtPointer(event)" in html
    assert ".nodeCanvasObject(drawNode)" in html
    assert "data.nodes.map(node => node.entity || 'Unassigned')" in html
    assert "rankNodes" in html
    assert "node.fx = rankOffsets.get(rank) - graphWidth / 2" in html
    assert "(index - (nodes.length - 1) / 2) * 70" in html
    assert "node.entityColor = entityColors.get(node.entity)" in html
    assert "item.textContent = entity" in html
    assert "'#ff9f43', '#2dd4bf', '#fb7185', '#a78bfa'" in html
    assert '"#b9c9d8"' in html
    assert "function linkRoute(link)" in html
    assert "const corners = [[bendX, start[1]], [bendX, end[1]]]" in html
    assert "2 * inverse * t * corner[0] + t * t * after[0]" in html
    assert ".linkCanvasObjectMode(() => 'replace')" in html
    assert ".linkDirectionalParticles(1)" in html
    assert "link.flowOffset = index / Math.max(1, data.links.length)" in html
    assert "performance.now() / 2200" in html
    assert ".linkCurvature(0.18)" not in html
    assert ".linkDirectionalParticles(2)" in html
    assert ".nodeColor(node => node.is_function ? functionColor : node.entityColor)" in html
    assert "function resizeGraph()" in html
    assert "health_signal_normalized" in html
    assert '"label": "bearing_temperature_max", "tags": [], "node_type": "feature"' in html
    assert '"is_function": false, "entity": "pump", "data_type": "float"' in html
    assert '"label": "operating_point_recommendation", "tags": [], "node_type": "feature"' in html
    assert '"is_function": false, "entity": "pump_telemetry"' in html
    assert 'aria-label="Feature graph legend"' in html
    assert "Function</span>" in html
    for category in ("Read", "Vectorize", "Collapse", "Conform", "Expand", "Write"):
        assert f"{category} function</span>" not in html
    assert 'class="details details-2d"' in html
    assert "Selected item" in html
    assert ".details-2d { right: auto; left: 16px;" in html
    assert "graph.screen2GraphCoords(" in html
    assert ".onNodeClick((_node, event) => selectAtPointer(event))" in html
    assert ".onBackgroundClick(event => selectAtPointer(event))" in html
    assert "<h2>Node details</h2>" not in html
    assert "3d-force-graph" in html
