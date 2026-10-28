import pathlib
import sys

import pytest
from conftest import EXAMPLES_ROOT, render_explorer

from uptimely import spec
from uptimely.cli import cli
from uptimely.spec.feature_graph import models

SPEC_PATH = EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json"


@pytest.mark.parametrize("verbose", [False, True])
def test_graph_cli_inspects_without_exporting(
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


def test_system_graph_connects_actions_to_feature_outputs() -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    system = spec.FeatureGraph(spec_definition)

    action_function_ids = {action.binding.function for action in system.actions}
    assert "maximum" in action_function_ids
    assert "normalize_health_signal" in action_function_ids
    assert "extract_recommendation_value" in action_function_ids
    assert "extract_converged_flag" not in action_function_ids
    assert "extract_convergence_flag" not in action_function_ids
    recommendation_nodes = [
        node
        for node in system.graph
        if isinstance(node.reference, models.ActionNode)
        and node.reference.function is not None
        and node.reference.function.id == "extract_recommendation_value"
    ]
    recommendation_outputs = {
        neighbor.reference.name
        for action_node in recommendation_nodes
        for neighbor, _attrs in system.graph.neighbors(action_node)
        if isinstance(neighbor.reference, models.FeatureNode)
    }
    assert recommendation_outputs == {
        "recommended_flow_rate",
        "recommended_discharge_pressure",
        "energy_cost_score",
        "converged",
    }
    assert set().union(*(set(node.reference.features) for node in recommendation_nodes)) == (
        recommendation_outputs
    )

    actual_edges = {
        (
            source.reference.action_id,
            neighbor_node.reference.name,
        )
        for source in system.graph
        if isinstance(source.reference, models.ActionNode)
        for neighbor_node, _attrs in system.graph.neighbors(source)
        if isinstance(neighbor_node.reference, models.FeatureNode)
    }

    assert ("bearing_temperature_by_pump", "bearing_temperature_max") in actual_edges
    assert ("health_signal_normalized", "health_signal_normalized") in actual_edges
    assert ("recommended_flow_rate", "recommended_flow_rate") in actual_edges
    assert ("recommended_discharge_pressure", "recommended_discharge_pressure") in actual_edges
    assert ("energy_cost_score", "energy_cost_score") in actual_edges
    assert ("converged", "converged") in actual_edges


def test_system_graph_contains_one_node_per_action() -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    system = spec.FeatureGraph(spec_definition)

    action_nodes = [
        node.reference for node in system.graph if isinstance(node.reference, models.ActionNode)
    ]
    spec_function_ids = set(system.spec.functions)
    action_count = sum(
        len(dataset.actions)
        for entity in spec_definition.entities.values()
        for dataset in entity.datasets.values()
    )

    assert len(action_nodes) == action_count
    assert any(action.action_id == "bearing_temperature_by_pump" for action in action_nodes)
    assert all(
        action.function is not None and action.function.id in spec_function_ids
        for action in action_nodes
    )
    assert len({action.node_id for action in action_nodes}) == action_count
    assert "bearing_temperature" in system.input_names
    assert all(isinstance(name, str) for name in system.input_names)

    graph_text = system.print_graph()
    assert "ActionNode(" not in graph_text
    assert "bearing_temperature_by_pump" in graph_text


def test_subset_raises_helpful_error_for_missing_output() -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    system = spec.FeatureGraph(spec_definition)

    with pytest.raises(ValueError, match=r"Unknown output feature\(s\): temperature_3"):
        system.subset(["temperature_3"])


@pytest.mark.parametrize("subset", [False, True])
def test_graph_rendering_and_explicit_printing(
    capsys: pytest.CaptureFixture[str], subset: bool
) -> None:
    system = spec.FeatureGraph(spec.load_spec(SPEC_PATH))
    graph = system.subset(["health_signal_normalized"]) if subset else system

    graph_text = graph.render_graph()
    assert "health_signal_normalized" in graph_text
    assert capsys.readouterr().out == ""

    assert graph.print_graph() == graph_text
    assert capsys.readouterr().out == graph_text + "\n"
    assert not hasattr(graph, "print")


def test_system_graph_builds_from_entity_feature_bindings() -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    system = spec.FeatureGraph(spec_definition)

    assert "bearing_temperature_max" in system.feature_names
    assert "health_signal_normalized" in system.feature_names


def test_dependency_features_keep_their_producer_entity_without_becoming_source_inputs() -> None:
    system = spec.FeatureGraph(spec.load_spec(SPEC_PATH))
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
    spec_definition = spec.load_spec(SPEC_PATH)
    render_explorer(spec_definition, tmp_path / "index.html")
    output = tmp_path / "spec/feature-lineage.html"
    html = output.read_text(encoding="utf-8")
    script = (tmp_path / "js/feature_lineage.js").read_text(encoding="utf-8")
    shared_script = (tmp_path / "js/graph_components.js").read_text(encoding="utf-8")

    assert output.exists()
    assert 'src="../js/feature_lineage.js"' in html
    assert "3d-force-graph" in html
    assert "SphereGeometry" in shared_script
    assert "ExplorerGraph.datasetNodeObject(node, node.label, style)" in script
    assert "ConeGeometry" not in script
    assert "OctahedronGeometry" in script
    assert "CylinderGeometry" not in script
    assert (
        "${node.is_action ? 'action' : 'feature'}: ${node.label}"
        r"\nentity: ${node.entity || 'n/a'}" in script
    )
    assert "entity: ${node.entity || 'n/a'}" in script
    assert "['Entity', formatDetailValue(entity)]" in script
    assert '"node_type": "feature"' in html
    assert '"is_action": true' in html
    assert '"is_action": false' in html
    assert "['Node type', 'Action']" in script
    assert "['Function', node.function_id || 'n/a']" in script
    assert "rows.push([outputLabel, formatDetailValue(features.join(', '))])" in script
    assert "ExplorerGraph.showDetails(nodeDetails, 'Selected item', rows)" in script
    assert 'src="../js/graph_components.js"' in html
    assert "document.createTextNode(value == null ? 'n/a' : String(value))" in shared_script
    assert "Action</span>" in html
    for category in ("Read", "Vectorize", "Collapse", "Conform", "Expand", "Write"):
        assert f"{category} function</span>" not in html
    assert "Datasets" in html
    assert '<span class="legend-heading">Entities' not in html
    assert "dataset-legend" in html
    assert "input_color" not in script


def test_website_includes_2d_lineage_html(tmp_path: pathlib.Path) -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    render_explorer(spec_definition, tmp_path / "index.html")
    output = tmp_path / "spec/feature-lineage.html"
    html = output.read_text(encoding="utf-8")
    script = (tmp_path / "js/feature_lineage.js").read_text(encoding="utf-8")
    shared_script = (tmp_path / "js/graph_components.js").read_text(encoding="utf-8")
    styles = (tmp_path / "css/graph.css").read_text(encoding="utf-8")

    assert 'src="../js/feature_lineage.js"' in html
    assert 'href="../css/graph.css"' in html
    assert "force-graph@1.52.0/dist/force-graph.min.js" in html
    assert "ForceGraph()(graphContainer)" in script
    assert "graph-hint" not in html
    assert 'id="reset-graph"' in html
    assert ">Reset graph</button>" in html
    assert "ExplorerGraph.prepareDatasetLayout(" in script
    assert "function prepareDatasetLayout(graphData, rankForNode, labelForNode)" in shared_script
    assert "function drawEntityLanes(ctx, globalScale)" not in script
    assert "function drawNode(node, ctx)" in script
    assert (
        "ExplorerGraph.selectCard(graph, graphContainer, data.nodes, event, updateDetails)"
        in script
    )
    assert ".nodeCanvasObject(drawNode)" in script
    assert "node.dataset_id || UNASSIGNED_DATASET" in shared_script
    assert "rankNodes" in script
    assert "node.fx = rankOffsets.get(rank) - graphWidth / 2" in shared_script
    assert "(index - (nodes.length - 1) / 2) * DATASET_LAYOUT.nodeSpacing" in shared_script
    assert "node.datasetColor = colors.get(node.dataset_id)" in shared_script
    assert "appendLegend(container, names.map(dataset =>" in shared_script
    assert "item.textContent = label" in shared_script
    assert "'#ff9f43', '#2dd4bf', '#fb7185', '#a78bfa'" in shared_script
    assert '"#b9c9d8"' in html
    assert "function datasetLinkRoute(link)" in shared_script
    assert "source.routeY" in shared_script
    assert "2 * inverse * t * corner[0] + t * t * after[0]" in shared_script
    assert ".linkCanvasObjectMode(() => 'replace')" in script
    assert "ExplorerGraph.createDatasetLinkRenderer(data, style, highlight)" in script
    assert ".linkDirectionalParticles(LINK_ROUTE.particleCount)" in script
    assert "link.flowOffset = index / Math.max(1, data.links.length)" in shared_script
    assert "performance.now() / LINK_ROUTE.flowDurationMs" in shared_script
    assert ".linkCurvature(0.18)" not in script
    assert ".linkDirectionalParticles(LINK_STYLE.particleCount)" in shared_script
    assert ".nodeColor(node => node.is_action ? functionColor : node.datasetColor)" in script
    assert (
        "ExplorerGraph.createView(graph, graphContainer, DATASET_LAYOUT.fitPadding, "
        "'2d', layout.bounds)" in script
    )
    assert "graph.width(container.clientWidth).height(container.clientHeight)" in shared_script
    assert "health_signal_normalized" in html
    assert '"label": "bearing_temperature_max", "tags": [], "node_type": "feature"' in html
    assert (
        '"is_action": false, "entity": "pump", "dataset_id": "pump_dataset", "data_type": "float"'
    ) in html
    assert '"label": "operating_point_recommendation", "tags": [], "node_type": "feature"' in html
    assert (
        '"is_action": false, "entity": "pump_telemetry", '
        '"dataset_id": "pump_telemetry_dataset"' in html
    )
    assert 'aria-label="Legend"' in html
    assert "Action</span>" in html
    for category in ("Read", "Vectorize", "Collapse", "Conform", "Expand", "Write"):
        assert f"{category} function</span>" not in html
    assert 'class="details details-2d"' in html
    assert "Selected item" in html
    assert ".details-2d { right: auto; left: 16px;" in styles
    assert "graph.screen2GraphCoords(" in shared_script
    assert ".onNodeClick((_node, event) => selectAtPointer(event))" in script
    assert ".onBackgroundClick(event => selectAtPointer(event))" in script
    assert "<h2>Node details</h2>" not in html
    assert "3d-force-graph" in html
