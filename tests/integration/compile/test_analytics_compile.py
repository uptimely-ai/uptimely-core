import json
import pathlib

import pytest

from uptimely import analytics, compile

ANALYTICS_PATH = pathlib.Path("examples/pump_analytics/_generated/analytics/analytics.json")


def test_compiler_creates_callable_graph_subset_for_requested_features() -> None:
    plan = compile.Compiler(ANALYTICS_PATH, features=["health_signal_normalized"]).compile()

    assert [
        callable.output
        for stage in plan.execution_stages
        for callable in stage
        if callable.operation == "vectorize"
    ] == [
        "health_signal_normalized",
    ]
    assert {callable.operation for callable in plan.callables} == {
        "read",
        "collapse",
        "vectorize",
    }
    assert {
        callable.output for callable in plan.callables if callable.operation == "vectorize"
    } == {
        "health_signal_normalized",
    }

    with pytest.raises(ValueError, match=r"Unknown output feature\(s\): missing"):
        compile.Compiler(ANALYTICS_PATH, features=["missing"]).compile()


def test_compiler_emits_one_operation_for_multi_output_mapping(tmp_path: pathlib.Path) -> None:
    analytics_definition = json.loads(ANALYTICS_PATH.read_text(encoding="utf-8"))
    dataset = analytics_definition["entities"]["pump"]["datasets"][0]
    mapping = dataset["mappings"]["health_signal_normalized"]
    mapping["features"]["outputs"].append("$features.health_signal_secondary")
    dataset["features"]["health_signal_secondary"] = {"type": "float"}
    analytics_path = tmp_path / "analytics.json"
    analytics_path.write_text(json.dumps(analytics_definition), encoding="utf-8")

    plan = compile.Compiler(analytics_path, features=["health_signal_normalized"]).compile()
    vectorize_callables = [
        callable for callable in plan.callables if callable.operation == "vectorize"
    ]

    assert len(vectorize_callables) == 1
    assert vectorize_callables[0].output_features == [
        "health_signal_normalized",
        "health_signal_secondary",
    ]


def test_callable_graph_subset_contains_requested_output_and_ancestors() -> None:
    graph = compile.CallableGraph(analytics.Analytics(json=ANALYTICS_PATH))

    subset = graph.subset(["health_signal_normalized"])
    normalized = next(
        node for node in subset.callables if node.feature == "health_signal_normalized"
    )

    assert [
        node.feature for node in subset.get_callable_order() if node.operation == "vectorize"
    ] == [
        "health_signal_normalized",
    ]
    assert {(node.operation, node.function_id) for node in subset.dependencies(normalized)} == {
        ("collapse", "maximum"),
    }
    assert len(graph.callables) == 13

    with pytest.raises(ValueError, match=r"Unknown output feature\(s\): missing"):
        graph.subset(["missing"])
