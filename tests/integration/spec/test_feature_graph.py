import dataclasses
import pathlib
import sys

import pytest
from support import examples as example_support

from uptimely import project, spec
from uptimely.cli import cli
from uptimely.spec import operator_kinds as functions
from uptimely.spec.feature_graph import models

SPEC_PATH = example_support.EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json"


def test_graph_metadata_follows_function_capabilities(
    monkeypatch: pytest.MonkeyPatch, pump_bundle: project.BuildBundle
) -> None:
    graph = spec.FeatureGraph(pump_bundle.spec_definition)
    original = graph._declared_features()
    catalog = dict(functions.OPERATOR_KINDS)
    catalog["read"] = dataclasses.replace(catalog["read"], is_source=False, is_transformer=True)
    catalog["collapse"] = dataclasses.replace(catalog["collapse"], dimension_change="preserve")
    monkeypatch.setattr(functions, "OPERATOR_KINDS", catalog)
    changed = graph._declared_features()
    checked = set()
    for key, operator in graph.spec.operator_items:
        kind = graph.spec.operator_kinds[key]
        if kind not in {"read", "collapse"}:
            continue
        checked.add(kind)
        for name in operator.output_features:
            if name in graph.spec.grain_key_ids:
                continue
            assert changed[name].is_source_input is not original[name].is_source_input
    assert checked == {"read", "collapse"}
    graph.spec = spec.Spec.model_validate(graph.spec.model_dump())
    for profile_id, profile in graph.spec.profiles.items():
        profile.assembly = {
            key: operator
            for key, operator in profile.assembly.items()
            if graph.spec.operator_kinds[(profile_id, key)] == "read"
        }
    graph.operators = graph.spec.operators
    rebuilt_features = [
        node.reference
        for node in graph._create_graph()
        if isinstance(node.reference, models.FeatureNode)
    ]
    assert rebuilt_features
    declared_types = {
        feature_id: feature.type
        for profile in graph.spec.profiles.values()
        for feature_id, feature in profile.features.items()
    }
    assert all(feature.data_type == declared_types[feature.name] for feature in rebuilt_features)


@pytest.mark.usefixtures("example_projects")
@pytest.mark.parametrize("debug", [False, True])
def test_graph_cli_inspects_without_exporting(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    debug: bool,
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
    if debug:
        arguments.extend(["--log-level", "debug"])
    monkeypatch.setattr(sys, "argv", arguments)
    monkeypatch.chdir(tmp_path)

    cli.main()

    output = capsys.readouterr().out
    assert "Feature graph:" in output
    assert "Selected feature subset: 2 features" in output
    assert ("Selected feature subset\n" in output) == debug
    assert not list(tmp_path.iterdir())


@pytest.mark.usefixtures("example_projects")
def test_system_graph_connects_operator_to_feature_outputs() -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    system = spec.FeatureGraph(spec_definition)

    operator_function_ids = {operator.compute.function for operator in system.operators}
    assert "aggregate" in operator_function_ids
    assert "min_max_scale" in operator_function_ids
    assert "extract_field" in operator_function_ids
    assert "LazyFrame.with_columns" in operator_function_ids
    assert "extract_converged_flag" not in operator_function_ids
    assert "extract_convergence_flag" not in operator_function_ids
    recommendation_nodes = [
        node
        for node in system.graph
        if isinstance(node.reference, models.OperatorNode)
        and node.reference.function.id == "extract_field"
    ]
    recommendation_outputs = {
        neighbor.reference.name
        for operator_node in recommendation_nodes
        for neighbor, _attrs in system.graph.neighbors(operator_node)
        if isinstance(neighbor.reference, models.FeatureNode)
    }
    assert recommendation_outputs == {
        "recommended_discharge_pressure",
        "energy_cost_score",
        "converged",
    }
    assert set().union(*(set(node.reference.features) for node in recommendation_nodes)) == (
        recommendation_outputs
    )

    actual_edges = {
        (
            source.reference.operator_id,
            neighbor_node.reference.name,
        )
        for source in system.graph
        if isinstance(source.reference, models.OperatorNode)
        for neighbor_node, _attrs in system.graph.neighbors(source)
        if isinstance(neighbor_node.reference, models.FeatureNode)
    }

    assert ("bearing_temperature_by_pump", "bearing_temperature_max") in actual_edges
    assert ("health_signal_normalized", "health_signal_normalized") in actual_edges
    assert ("recommended_flow_rate", "recommended_flow_rate") in actual_edges
    assert ("recommended_discharge_pressure", "recommended_discharge_pressure") in actual_edges
    assert ("energy_cost_score", "energy_cost_score") in actual_edges
    assert ("converged", "converged") in actual_edges


@pytest.mark.usefixtures("example_projects")
def test_system_graph_contains_one_node_per_operator() -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    system = spec.FeatureGraph(spec_definition)

    operator_nodes = [
        node.reference for node in system.graph if isinstance(node.reference, models.OperatorNode)
    ]
    spec_function_ids = set(system.spec.functions)
    operator_count = sum(len(profile.assembly) for profile in spec_definition.profiles.values())
    assert len(operator_nodes) == operator_count
    assert any(operator.operator_id == "bearing_temperature_by_pump" for operator in operator_nodes)
    assert all(operator.function.id in spec_function_ids for operator in operator_nodes)
    assert len({operator.node_id for operator in operator_nodes}) == operator_count
    assert system.feature_nodes == tuple(
        node.reference for node in system.graph if isinstance(node.reference, models.FeatureNode)
    )
    subset = system.subset(["health_signal_normalized"])
    assert subset.feature_nodes == tuple(
        node.reference for node in subset.graph if isinstance(node.reference, models.FeatureNode)
    )
    assert {feature.name for feature in subset.feature_nodes} <= {
        feature.name for feature in system.feature_nodes
    }
    assert "bearing_temperature" in system.input_names
    assert all(isinstance(name, str) for name in system.input_names)

    graph_text = system.print_graph()
    assert "OperatorNode(" not in graph_text
    assert "bearing_temperature_by_pump" in graph_text


@pytest.mark.usefixtures("example_projects")
def test_subset_raises_helpful_error_for_missing_output() -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    system = spec.FeatureGraph(spec_definition)

    with pytest.raises(ValueError, match=r"Unknown output feature\(s\): temperature_3"):
        system.subset(["temperature_3"])


@pytest.mark.usefixtures("example_projects")
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


@pytest.mark.usefixtures("example_projects")
def test_system_graph_builds_from_profile_feature_bindings() -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    system = spec.FeatureGraph(spec_definition)

    assert "bearing_temperature_max" in system.feature_names
    assert "health_signal_normalized" in system.feature_names


@pytest.mark.usefixtures("example_projects")
def test_dependency_features_keep_their_producer_profile_without_becoming_source_inputs() -> None:
    system = spec.FeatureGraph(spec.load_spec(SPEC_PATH))
    features = {
        node.reference.name: node.reference
        for node in system.graph
        if isinstance(node.reference, models.FeatureNode)
    }

    assert features["bearing_temperature_max"].profile_id == "pump"
    assert features["operating_point_recommendation"].profile_id == "pump_telemetry"
    assert features["bearing_temperature_max"].is_source_input is False
    assert features["operating_point_recommendation"].is_source_input is False
