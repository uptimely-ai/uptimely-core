import json
import pathlib

import pytest

from uptimely import compile, spec

SPEC_PATH = pathlib.Path("examples/pump_analytics/_generated/spec/spec.json")


def test_compiler_creates_callable_graph_subset_for_requested_features() -> None:
    plan = compile.Compiler(SPEC_PATH, features=["health_signal_normalized"]).compile()

    assert [
        operation.output
        for stage in plan.execution_stages
        for operation in stage
        if operation.kind == "vectorize"
    ] == [
        "health_signal_normalized",
    ]
    assert {operation.kind for operation in plan.operations} == {
        "read",
        "collapse",
        "vectorize",
    }
    assert {operation.output for operation in plan.operations if operation.kind == "vectorize"} == {
        "health_signal_normalized",
    }

    with pytest.raises(ValueError, match=r"Unknown output feature\(s\): missing"):
        compile.Compiler(SPEC_PATH, features=["missing"]).compile()


def test_compiler_emits_one_operation_for_multi_output_mapping(tmp_path: pathlib.Path) -> None:
    specification = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    dataset = specification["entities"]["pump"]["datasets"][0]
    mapping = dataset["mappings"]["health_signal_normalized"]
    mapping["features"]["outputs"].append("$features.health_signal_secondary")
    dataset["features"]["health_signal_secondary"] = {"type": "float"}
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(specification), encoding="utf-8")

    plan = compile.Compiler(spec_path, features=["health_signal_normalized"]).compile()
    vectorize_operations = [
        operation for operation in plan.operations if operation.kind == "vectorize"
    ]

    assert len(vectorize_operations) == 1
    assert vectorize_operations[0].output_features == [
        "health_signal_normalized",
        "health_signal_secondary",
    ]


def test_callable_graph_subset_contains_requested_output_and_ancestors() -> None:
    graph = compile.CallableGraph(spec.Specification.from_json(SPEC_PATH))

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
        ("collapse", "maximum"),
    }
    assert len(graph.callables) == 13

    with pytest.raises(ValueError, match=r"Unknown output feature\(s\): missing"):
        graph.subset(["missing"])
