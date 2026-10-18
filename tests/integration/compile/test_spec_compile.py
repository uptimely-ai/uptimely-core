import json
import pathlib

import pytest
from conftest import EXAMPLES_ROOT

from uptimely import compiler, spec

SPEC_PATH = EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json"


def test_compiler_creates_callable_graph_subset_for_requested_features() -> None:
    plan = compiler.Compiler(SPEC_PATH, features=["health_signal_normalized"]).compile()

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
        compiler.Compiler(SPEC_PATH, features=["missing"]).compile()


def test_compiler_emits_one_operation_for_multi_output_mapping(tmp_path: pathlib.Path) -> None:
    spec_definition = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    dataset = spec_definition["entities"]["pump"]["datasets"][0]
    mapping = dataset["mappings"]["health_signal_normalized"]
    mapping["features"]["outputs"].append("$features.health_signal_secondary")
    dataset["features"]["health_signal_secondary"] = {"type": "float"}
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec_definition), encoding="utf-8")

    plan = compiler.Compiler(spec_path, features=["health_signal_normalized"]).compile()
    vectorize_callables = [
        callable for callable in plan.callables if callable.operation == "vectorize"
    ]

    assert len(vectorize_callables) == 1
    assert vectorize_callables[0].output_features == [
        "health_signal_normalized",
        "health_signal_secondary",
    ]


def test_callable_graph_subset_contains_requested_output_and_ancestors() -> None:
    graph = compiler.CallableGraph(spec.load_spec(SPEC_PATH))

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


def test_compiled_inputs_match_each_entity_dataset_mapping() -> None:
    document = spec.load_spec(SPEC_PATH)
    execution_plan = compiler.Compiler(document).compile()
    datasets = {
        (entity_id, dataset.id): dataset
        for entity_id, entity in document.entities.items()
        for dataset in entity.datasets
    }

    assert len(datasets) > 1
    assert len({entity_id for entity_id, _ in datasets}) > 1
    for callable in execution_plan.callables:
        mapping_id = callable.id.rsplit(":", 1)[1]
        mapping = datasets[callable.entity_id, callable.dataset_id].mappings[mapping_id]
        assert callable.input_features == mapping.input_features
        assert callable.output_features == mapping.output_features


def test_graph_subset_retains_validated_dataset_mapping_lookups() -> None:
    document = spec.load_spec(SPEC_PATH)
    graph = compiler.CallableGraph(document)
    subset = graph.subset(["health_signal_normalized"])

    for node in subset.callables:
        assert subset.dataset_for(node) is graph.dataset_for(node)
        assert subset.mapping_for(node) is graph.mapping_for(node)


def test_graph_rejects_duplicate_datasets_before_indexing() -> None:
    document = spec.load_spec(SPEC_PATH)
    entities = list(document.entities.values())
    entities[1].datasets[0].id = entities[0].datasets[0].id

    with pytest.raises(ValueError, match="Duplicate dataset id"):
        compiler.CallableGraph(document)
