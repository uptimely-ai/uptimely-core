import json
import pathlib

import pytest
from conftest import EXAMPLES_ROOT

from uptimely import compiler, spec
from uptimely import execution_plan as compiler_plan
from uptimely.compiler import inspection
from uptimely.spec import model as spec_model

SPEC_PATH = EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json"
pytestmark = pytest.mark.usefixtures("example_projects")


def _add_escape_mapping(
    configuration: dict,
    mapping_id: str,
    function_id: str,
    output_features: list[str],
    input_features: list[str],
    entrypoint: str,
    *,
    dataframe_dataset: str | None = None,
) -> None:
    """Add one escape action and its function and output declarations."""
    dataset = configuration["entities"]["pump_telemetry"]["datasets"]["pump_telemetry_dataset"]
    dataset["features"].update({feature_id: {"type": "float"} for feature_id in output_features})
    arguments = {"source": {"type": "dataframe"}} if dataframe_dataset is not None else {}
    configuration["functions"][function_id] = {
        "kind": "escape",
        "returns": "any",
        "entrypoint": entrypoint,
        "args": arguments,
    }
    configuration["entities"]["pump_telemetry"]["datasets"]["pump_telemetry_dataset"]["actions"][
        mapping_id
    ] = {
        "binding": {
            "function": function_id,
            "args": (
                {"source": f"$datasets.{dataframe_dataset}.dataframe"}
                if dataframe_dataset is not None
                else {}
            ),
        },
        "features": {
            "inputs": [f"$features.{feature_id}" for feature_id in input_features],
            "outputs": [f"$features.{feature_id}" for feature_id in output_features],
        },
    }


def _escape_spec_configuration() -> dict:
    """Return a valid pump spec with chained, multi-output, and unrelated escapes."""
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    entrypoint = "examples.pump_analytics.functions.analytics:maximum"
    _add_escape_mapping(
        configuration,
        "escape_start",
        "escape_start",
        ["external_first", "external_second"],
        ["bearing_temperature"],
        entrypoint,
        dataframe_dataset="pump_dataset",
    )
    _add_escape_mapping(
        configuration,
        "escape_chain",
        "escape_chain",
        ["external_third"],
        ["external_first"],
        entrypoint,
    )
    _add_escape_mapping(
        configuration,
        "escape_unrelated",
        "escape_unrelated",
        ["external_unrelated"],
        ["bearing_temperature"],
        entrypoint,
    )
    return configuration


def test_compilation_preserves_the_saved_plan() -> None:
    expected = json.loads(SPEC_PATH.with_name("execution_plan.json").read_text(encoding="utf-8"))
    actual = compiler_plan.to_dict(compiler.Compiler().compile(spec.load_spec(SPEC_PATH)))

    assert actual.keys() == expected.keys()
    assert actual["plan_version"] == expected["plan_version"]
    assert actual["required_backend"] == expected["required_backend"]
    assert actual["resources"]["signatures"] == expected["resources"]["signatures"]
    assert actual["resources"]["entrypoint_packages"]
    assert {
        item["id"]: item | {"dependency_ids": sorted(item["dependency_ids"])}
        for item in actual["invocations"]
    } == {
        item["id"]: item | {"dependency_ids": sorted(item["dependency_ids"])}
        for item in expected["invocations"]
    }
    assert [set(stage) for stage in actual["stages"]] == [
        set(stage) for stage in expected["stages"]
    ]


def test_dataset_dimension_selector_is_resolved_in_the_portable_plan(
    tmp_path: pathlib.Path,
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    function = configuration["functions"]["read_pump_telemetry"]
    function["validate_signature"] = False
    function["args"]["keys"] = {"type": "array[string]"}
    function["args"]["source_keys"] = {"type": "array[string]"}
    dataset = configuration["entities"]["pump_telemetry"]["datasets"]["pump_telemetry_dataset"]
    dataset["actions"]["read_pump_telemetry"]["binding"]["args"].update(
        {
            "keys": "$datasets.@.dimensions.ids",
            "source_keys": "$datasets.pump_dataset.dimensions.ids",
        }
    )
    path = tmp_path / "dimension_keys.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")

    definition = spec.load_spec(path)
    plan = compiler.Compiler().compile(definition)
    invocation = next(
        item for item in plan.invocations if item.function_id == "read_pump_telemetry"
    )
    expected = definition.dimension_ids_by_dataset["pump_telemetry_dataset"]
    expected_source = definition.dimension_ids_by_dataset["pump_dataset"]

    assert invocation.arguments["keys"] == expected
    assert invocation.arguments["source_keys"] == expected_source
    portable = compiler_plan.to_dict(plan)
    portable_invocation = next(
        item for item in portable["invocations"] if item["function_id"] == "read_pump_telemetry"
    )
    assert portable_invocation["arguments"]["keys"] == expected
    assert portable_invocation["arguments"]["source_keys"] == expected_source


def test_collapse_feature_placeholder_uses_invocation_feature_id(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    action = configuration["entities"]["pump"]["datasets"]["pump_dataset"]["actions"][
        "bearing_temperature_by_pump"
    ]
    action["binding"]["args"]["output"] = "$features.@.id"
    path = tmp_path / "collapse_feature_placeholder.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")

    definition = spec.load_spec(path)
    graph = compiler.InvocationGraph(definition)
    node = next(
        item for item in graph.invocations if item.mapping_id == "bearing_temperature_by_pump"
    )
    plan = compiler.Compiler().compile(definition)
    invocation = next(
        item for item in plan.invocations if item.mapping_id == "bearing_temperature_by_pump"
    )

    assert node.feature_id == "bearing_temperature_max"
    assert invocation.arguments["output"] == node.feature_id


def test_compiler_keeps_reused_function_mappings_as_distinct_invocations() -> None:
    plan = compiler.Compiler().compile(spec.load_spec(SPEC_PATH))
    invocations = [
        invocation
        for invocation in plan.invocations
        if invocation.function_id == "extract_recommendation_value"
    ]

    assert {feature for invocation in invocations for feature in invocation.output_features} == {
        "recommended_flow_rate",
        "recommended_discharge_pressure",
        "energy_cost_score",
        "converged",
    }
    assert len(invocations) == 4
    assert len({invocation.id for invocation in invocations}) == 4


def test_compiler_emits_conform_invocation_with_its_dataset_dependency() -> None:
    definition = spec.load_spec(SPEC_PATH)
    pump_entity = definition.entities["pump"]
    pump_dataset = pump_entity.datasets["pump_dataset"]
    read_mapping = (
        definition.entities["pump_telemetry"]
        .datasets["pump_telemetry_dataset"]
        .actions["read_pump_telemetry"]
    )

    definition.entities["auxiliary_entity"] = spec_model.Entity(
        id="auxiliary_entity",
        name="Auxiliary",
        dimensions=pump_entity.dimensions,
        datasets={
            "auxiliary_dataset": spec_model.Dataset(
                id="auxiliary_dataset",
                features={"auxiliary_value": spec_model.Feature(id="auxiliary_value")},
                actions={
                    "read_auxiliary": spec_model.Action(
                        id="read_auxiliary",
                        binding=spec_model.Binding(
                            function="read_pump_telemetry",
                            args=dict(read_mapping.binding.args),
                        ),
                        features=spec_model.ActionFeatures(outputs=["$features.auxiliary_value"]),
                    ),
                },
            )
        },
    )
    pump_dataset.features["conformed_auxiliary"] = spec_model.Feature(id="conformed_auxiliary")
    pump_dataset.actions["conform_auxiliary"] = spec_model.Action(
        id="conform_auxiliary",
        binding=spec_model.Binding(
            function="conform_auxiliary",
            args={
                "source": "$datasets.auxiliary_dataset.dataframe",
            },
        ),
        features=spec_model.ActionFeatures(
            inputs=["$features.auxiliary_value"],
            outputs=["$features.conformed_auxiliary"],
        ),
    )
    definition.functions.root["conform_auxiliary"] = spec_model.FunctionTemplate(
        id="conform_auxiliary",
        kind="conform",
        returns="dataframe",
        entrypoint="examples.pump_analytics.functions.analytics:maximum",
        validate_signature=False,
        args={
            "source": spec_model.Argument(id="source", type="dataframe"),
        },
    )

    plan = compiler.Compiler().compile(definition, features=["conformed_auxiliary"])
    conform = next(
        invocation for invocation in plan.invocations if invocation.function_kind == "conform"
    )
    source = next(
        invocation for invocation in plan.invocations if invocation.mapping_id == "read_auxiliary"
    )
    stage_by_id = {
        invocation_id: index for index, stage in enumerate(plan.stages) for invocation_id in stage
    }

    assert source.id in conform.dependency_ids
    assert stage_by_id[source.id] < stage_by_id[conform.id]
    restored = compiler_plan.from_dict(json.loads(json.dumps(compiler_plan.to_dict(plan))))
    assert restored == plan


def test_compiler_creates_invocation_graph_subset_for_requested_features() -> None:
    plan = compiler.Compiler().compile(
        spec.load_spec(SPEC_PATH), features=["health_signal_normalized"]
    )

    assert [
        feature
        for stage in plan.execution_stages
        for invocation in stage
        if invocation.function_kind == "vectorize"
        for feature in invocation.output_features
    ] == [
        "health_signal_normalized",
    ]
    assert {invocation.function_kind for invocation in plan.invocations} == {
        "read",
        "collapse",
        "vectorize",
    }
    assert {
        feature
        for invocation in plan.invocations
        if invocation.function_kind == "vectorize"
        for feature in invocation.output_features
    } == {
        "health_signal_normalized",
    }

    with pytest.raises(ValueError, match=r"Unknown output feature\(s\): missing"):
        compiler.Compiler().compile(spec.load_spec(SPEC_PATH), features=["missing"])


def test_compiler_emits_one_operation_for_multi_output_mapping(tmp_path: pathlib.Path) -> None:
    spec_definition = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    dataset = spec_definition["entities"]["pump"]["datasets"]["pump_dataset"]
    action = dataset["actions"]["health_signal_normalized"]
    action["features"]["outputs"].append("$features.health_signal_secondary")
    dataset["features"]["health_signal_secondary"] = {"type": "float"}
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec_definition), encoding="utf-8")

    plan = compiler.Compiler().compile(
        spec.load_spec(spec_path), features=["health_signal_normalized"]
    )
    vectorize_invocations = [
        invocation for invocation in plan.invocations if invocation.function_kind == "vectorize"
    ]

    assert len(vectorize_invocations) == 1
    assert vectorize_invocations[0].output_features == [
        "health_signal_normalized",
        "health_signal_secondary",
    ]


def test_escape_dependencies_and_feature_selection_are_explicit(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "escape_spec.json"
    path.write_text(json.dumps(_escape_spec_configuration()), encoding="utf-8")
    document = spec.load_spec(path)
    graph = compiler.InvocationGraph(document)
    by_mapping = {node.mapping_id: node for node in graph.invocations}

    assert {
        node.mapping_id
        for node in graph.invocations
        if document.functions[node.function_id].kind == "escape"
    } == {
        "escape_start",
        "escape_chain",
        "escape_unrelated",
        "process_pump_external_workflow",
    }
    assert {
        dependency.mapping_id for dependency in graph.dependencies(by_mapping["escape_start"])
    } == {"read_pump_telemetry", "bearing_temperature_by_pump"}
    assert {
        dependency.mapping_id for dependency in graph.dependencies(by_mapping["escape_chain"])
    } == {"escape_start"}
    assert {
        dependency.mapping_id for dependency in graph.dependencies(by_mapping["escape_unrelated"])
    } == {"read_pump_telemetry"}

    escape_ids = {
        node.node_id
        for node in by_mapping.values()
        if document.functions[node.function_id].kind == "escape"
    }
    for node in graph.invocations:
        if document.functions[node.function_id].kind in {"vectorize", "write"}:
            assert not escape_ids.intersection(
                dependency.node_id for dependency in graph.dependencies(node)
            )

    for feature_id, expected_mappings in (
        ("external_first", {"escape_start"}),
        ("external_second", {"escape_start"}),
        ("external_third", {"escape_start", "escape_chain"}),
        ("external_unrelated", {"escape_unrelated"}),
    ):
        subset = graph.subset([feature_id])
        assert {
            node.mapping_id
            for node in subset.invocations
            if document.functions[node.function_id].kind == "escape"
        } == expected_mappings

    selected = compiler.Compiler().compile(document, features=["external_third"])
    selected_escape_mappings = {
        invocation.mapping_id
        for invocation in selected.invocations
        if invocation.function_kind == "escape"
    }
    assert selected_escape_mappings == {"escape_start", "escape_chain"}
    selected_start = next(
        invocation for invocation in selected.invocations if invocation.mapping_id == "escape_start"
    )
    assert selected_start.output_features == ["external_first", "external_second"]
    selected_by_id = selected.invocations_by_id
    assert {
        selected_by_id[dependency_id].mapping_id for dependency_id in selected_start.dependency_ids
    } == {
        "read_pump_telemetry",
        "bearing_temperature_by_pump",
    }

    stages = selected.execution_stages
    stage_by_mapping = {
        invocation.mapping_id: stage_index
        for stage_index, stage in enumerate(stages)
        for invocation in stage
        if invocation.function_kind == "escape"
    }
    assert stage_by_mapping["escape_start"] < stage_by_mapping["escape_chain"]
    stage_by_id = {
        invocation.id: stage_index
        for stage_index, stage in enumerate(stages)
        for invocation in stage
    }
    assert all(
        stage_by_id[dependency] < stage_by_id[selected_start.id]
        for dependency in selected_start.dependency_ids
    )
    assert all(dependency in selected_by_id for dependency in selected_start.dependency_ids)

    restored = compiler_plan.from_dict(json.loads(json.dumps(compiler_plan.to_dict(selected))))
    assert restored == selected
    assert restored.invocations == selected.invocations


def test_escape_return_annotations_do_not_constrain_compilation(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_name = f"escape_functions_{tmp_path.name.replace('-', '_')}"
    module_path = tmp_path / f"{module_name}.py"
    module_path.write_text(
        "import polars as pl\n"
        "def returns_none() -> None:\n    raise RuntimeError('must not run')\n"
        "def returns_scalar() -> int:\n    raise RuntimeError('must not run')\n"
        "def returns_object() -> object:\n    raise RuntimeError('must not run')\n"
        "def returns_dataframe() -> pl.DataFrame:\n    raise RuntimeError('must not run')\n"
        "def returns_unannotated():\n    raise RuntimeError('must not run')\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    for function_id in (
        "returns_none",
        "returns_scalar",
        "returns_object",
        "returns_dataframe",
        "returns_unannotated",
    ):
        _add_escape_mapping(
            configuration,
            function_id,
            function_id,
            [f"output_{function_id}"],
            ["bearing_temperature"],
            f"{module_name}:{function_id}",
        )
    path = tmp_path / "escape_signatures.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")

    compiled = compiler.Compiler().compile(spec.load_spec(path))
    escaped = {invocation.function_id: invocation for invocation in compiled.invocations}

    assert {
        function_id: compiled.resources["signatures"][invocation.id]
        for function_id, invocation in escaped.items()
        if function_id
        in {
            "returns_none",
            "returns_scalar",
            "returns_object",
            "returns_dataframe",
            "returns_unannotated",
        }
    } == {
        "returns_none": "None",
        "returns_scalar": "int",
        "returns_object": "object",
        "returns_dataframe": "DataFrame",
        "returns_unannotated": None,
    }
    assert {
        invocation.output_features[0]
        for invocation in compiled.invocations
        if invocation.function_kind == "escape"
    } == {
        "output_returns_none",
        "output_returns_scalar",
        "output_returns_object",
        "output_returns_dataframe",
        "output_returns_unannotated",
        "ratio",
    }


def test_controlled_function_return_annotations_remain_validated() -> None:
    function = spec.load_spec(SPEC_PATH).functions["pressure_flow_efficiency"]

    with pytest.raises(ValueError, match="expected DataFrame or LazyFrame"):
        inspection.validate_return_annotation(function, "int")


def test_invocation_graph_subset_contains_requested_output_and_ancestors() -> None:
    graph = compiler.InvocationGraph(spec.load_spec(SPEC_PATH))

    subset = graph.subset(["health_signal_normalized"])
    normalized = next(
        node for node in subset.invocations if node.feature_id == "health_signal_normalized"
    )

    assert [
        node.feature_id
        for node in subset.get_invocation_order()
        if graph.spec.functions[node.function_id].kind == "vectorize"
    ] == [
        "health_signal_normalized",
    ]
    assert {
        (graph.spec.functions[node.function_id].kind, node.function_id)
        for node in subset.dependencies(normalized)
    } == {
        ("collapse", "maximum"),
    }
    assert len(graph.invocations) == 16

    with pytest.raises(ValueError, match=r"Unknown output feature\(s\): missing"):
        graph.subset(["missing"])


def test_compiled_inputs_match_each_entity_dataset_mapping() -> None:
    document = spec.load_spec(SPEC_PATH)
    execution_plan = compiler.Compiler().compile(document)
    datasets = {
        (entity_id, dataset.id): dataset
        for entity_id, entity in document.entities.items()
        for dataset in entity.datasets.values()
    }

    assert len(datasets) > 1
    assert len({entity_id for entity_id, _ in datasets}) > 1
    for invocation in execution_plan.invocations:
        action = datasets[invocation.entity_id, invocation.dataset_id].actions[
            invocation.mapping_id
        ]
        assert invocation.input_features == action.input_features
        assert invocation.output_features == action.output_features


def test_graph_subset_retains_dataset_mapping_lookups() -> None:
    document = spec.load_spec(SPEC_PATH)
    graph = compiler.InvocationGraph(document)
    subset = graph.subset(["health_signal_normalized"])

    for node in subset.invocations:
        assert (
            graph.dataset_for(node) is document.entities[node.entity_id].datasets[node.dataset_id]
        )
        assert subset.dataset_for(node) is graph.dataset_for(node)
        assert subset.action_for(node) is graph.action_for(node)
        assert {dependency.node_id for dependency in subset.dependencies(node)} == {
            dependency.node_id for dependency in graph.dependencies(node)
        }

    nested_subset = subset.subset(["health_signal_normalized"])
    assert {node.node_id for node in nested_subset.invocations} == {
        node.node_id for node in subset.invocations
    }


def test_graph_rejects_duplicate_datasets_before_indexing() -> None:
    document = spec.load_spec(SPEC_PATH)
    entities = list(document.entities.values())
    dataset = next(iter(entities[0].datasets.values()))
    entities[1].datasets[dataset.id] = dataset.model_copy(deep=True)

    with pytest.raises(ValueError, match="Duplicate dataset id"):
        compiler.Compiler().compile(document)
