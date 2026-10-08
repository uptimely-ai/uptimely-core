from pathlib import Path

import pytest

from uptimely.compile import CallableGraph, Compiler
from uptimely.spec import Specification

SPEC_PATH = Path("examples/example_1/generated/spec/spec.json")


def test_compiler_creates_callable_graph_subset_for_requested_features() -> None:
    plan = Compiler(SPEC_PATH, features=["health_signal_normalized"]).compile()

    assert [
        node.feature for node in plan.execution_order if node.operation_type == "vectorize"
    ] == [
        "health_signal_normalized",
    ]
    assert {node.operation_type for node in plan.callable_graph.callables} == {
        "read",
        "collapse",
        "vectorize",
    }
    assert {
        node.feature for node in plan.callable_graph.callables if node.operation_type == "vectorize"
    } == {
        "health_signal_normalized",
    }

    with pytest.raises(ValueError, match=r"Unknown output feature\(s\): missing"):
        Compiler(SPEC_PATH, features=["missing"]).compile()


def test_callable_graph_subset_contains_requested_output_and_ancestors() -> None:
    graph = CallableGraph(Specification.from_json(SPEC_PATH))

    subset = graph.subset(["health_signal_normalized"])
    normalized = next(
        node for node in subset.callables if node.feature == "health_signal_normalized"
    )

    assert [
        node.feature for node in subset.get_callable_order() if node.operation_type == "vectorize"
    ] == [
        "health_signal_normalized",
    ]
    assert {
        (node.operation_type, node.function_id) for node in subset.dependencies(normalized)
    } == {
        ("collapse", "aggregate_by_dimension"),
    }
    assert len(graph.callables) == 13

    with pytest.raises(ValueError, match=r"Unknown output feature\(s\): missing"):
        graph.subset(["missing"])
