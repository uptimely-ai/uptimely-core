import dataclasses
import json
import pathlib
import types

import pytest
from support import examples as example_support

from uptimely import compiler, entrypoint, spec
from uptimely import execution_plan as compiler_plan
from uptimely.compiler import validation
from uptimely.spec import functions
from uptimely.spec import model as spec_model

SPEC_PATH = example_support.EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json"
pytestmark = pytest.mark.usefixtures("example_projects")


def _add_escape_mapping(
    configuration: dict,
    mapping_id: str,
    function_id: str,
    input_features: list[str],
    entrypoint: str,
    output_features: list[str] | None = None,
) -> None:
    """Add one escape action with logical feature dependencies."""
    configuration["functions"][function_id] = {
        "kind": "escape",
        "returns": "any",
        "entrypoint": entrypoint,
        "args": {},
    }
    configuration["profiles"]["pump_telemetry"]["assembly"][mapping_id] = {
        "compute": {
            "function": function_id,
            "args": {},
        },
        "interface": {
            "inputs": [f"$features.{feature_id}" for feature_id in input_features],
            "outputs": [f"$features.{feature_id}" for feature_id in (output_features or [])],
        },
    }


def _escape_spec_configuration() -> dict:
    """Return a valid pump spec with input-only, output-only, and chained escapes."""
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    dataset = configuration["profiles"]["pump_telemetry"]
    dataset["features"]["escape_start_output"] = {"type": "float"}
    dataset["features"]["escape_chain_output"] = {"type": "float"}
    dataset["features"]["escape_source_output"] = {"type": "float"}
    entrypoint = (
        "examples.pump_analytics.functions.external_workflow:process_pump_external_workflow"
    )
    _add_escape_mapping(
        configuration,
        "escape_start",
        "escape_start",
        ["bearing_temperature"],
        entrypoint,
        ["escape_start_output"],
    )
    _add_escape_mapping(
        configuration,
        "escape_chain",
        "escape_chain",
        ["escape_start_output"],
        entrypoint,
        ["escape_chain_output"],
    )
    _add_escape_mapping(
        configuration,
        "escape_unrelated",
        "escape_unrelated",
        ["bearing_temperature"],
        entrypoint,
    )
    _add_escape_mapping(
        configuration,
        "escape_source",
        "escape_source",
        [],
        entrypoint,
        ["escape_source_output"],
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
    dataset = configuration["profiles"]["pump_telemetry"]
    dataset["assembly"]["read_pump_telemetry"]["compute"]["args"].update(
        {
            "keys": "$profiles.@.grain.ids",
            "source_keys": "$profiles.pump_profile.grain.ids",
        }
    )
    path = tmp_path / "dimension_keys.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")

    definition = spec.load_spec(path)
    plan = compiler.Compiler().compile(definition)
    invocation = next(
        item for item in plan.invocations if item.function_id == "read_pump_telemetry"
    )
    expected = definition.grain_keys_by_profile["pump_telemetry"]
    expected_source = definition.grain_keys_by_profile["pump_profile"]

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
    operator = configuration["profiles"]["pump_profile"]["assembly"]["bearing_temperature_by_pump"]
    operator["compute"]["args"]["output"] = "$features.@.id"
    path = tmp_path / "collapse_feature_placeholder.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")

    definition = spec.load_spec(path)
    graph = compiler.InvocationGraph(definition)
    node = next(
        item for item in graph.invocations if item.action_id == "bearing_temperature_by_pump"
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
        invocation for invocation in plan.invocations if invocation.function_id == "extract_field"
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
    pump_profile = definition.profiles["pump_profile"]
    pump_profile = pump_profile
    read_mapping = definition.profiles["pump_telemetry"].assembly["read_pump_telemetry"]

    definition.profiles["auxiliary_dataset"] = spec_model.Profile(
        id="auxiliary_dataset",
        grain=list(pump_profile.grain),
        features={"auxiliary_value": spec_model.Feature(id="auxiliary_value")},
        assembly={
            "read_auxiliary": spec_model.Operator(
                id="read_auxiliary",
                compute=spec_model.Binding(
                    function="read_pump_telemetry",
                    args=dict(read_mapping.compute.args),
                ),
                interface=spec_model.Interface(outputs=["$features.auxiliary_value"]),
            ),
        },
    )
    pump_profile.features["conformed_auxiliary"] = spec_model.Feature(id="conformed_auxiliary")
    pump_profile.assembly["conform_auxiliary"] = spec_model.Operator(
        id="conform_auxiliary",
        compute=spec_model.Binding(
            function="conform_auxiliary",
            args={
                "source": "$profiles.auxiliary_dataset.dataframe",
            },
        ),
        interface=spec_model.Interface(
            inputs=["$features.auxiliary_value"],
            outputs=["$features.conformed_auxiliary"],
        ),
    )
    definition.functions.root["conform_auxiliary"] = spec_model.FunctionTemplate(
        id="conform_auxiliary",
        kind="conform",
        returns="dataframe",
        entrypoint="examples.pump_analytics.functions.analytics:aggregate",
        validate_signature=False,
        args={
            "source": spec_model.Argument(id="source", type="dataframe"),
        },
    )

    definition = spec_model.Spec.model_validate(definition.model_dump())
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
        "expand",
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
    dataset = spec_definition["profiles"]["pump_profile"]
    operator = dataset["assembly"]["health_signal_normalized"]
    operator["interface"]["outputs"].append("$features.health_signal_secondary")
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


def test_escape_inputs_and_outputs_define_logical_dependencies(
    tmp_path: pathlib.Path,
) -> None:
    path = tmp_path / "escape_spec.json"
    path.write_text(json.dumps(_escape_spec_configuration()), encoding="utf-8")
    document = spec.load_spec(path)
    graph = compiler.InvocationGraph(document)
    by_action = {node.action_id: node for node in graph.invocations}

    assert {
        node.action_id
        for node in graph.invocations
        if document.functions[node.function_id].kind == "escape"
    } == {
        "escape_start",
        "escape_chain",
        "escape_unrelated",
        "escape_source",
        "process_pump_external_workflow",
    }
    assert {
        dependency.action_id for dependency in graph.dependencies(by_action["escape_start"])
    } == {"read_pump_telemetry"}
    assert {
        dependency.action_id for dependency in graph.dependencies(by_action["escape_chain"])
    } == {"escape_start"}

    assert {
        dependency.action_id for dependency in graph.dependencies(by_action["escape_unrelated"])
    } == {"read_pump_telemetry"}
    assert graph.dependencies(by_action["escape_source"]) == []
    assert by_action["escape_start"].output_features == ("escape_start_output",)
    assert by_action["escape_chain"].output_features == ("escape_chain_output",)
    assert by_action["escape_source"].input_features == ()
    assert by_action["escape_source"].output_features == ("escape_source_output",)
    assert {
        "escape_chain_output",
        "escape_source_output",
    } <= spec.FeatureGraph(document).feature_names
    feature_subset = graph.subset(["escape_chain_output"])
    assert {"escape_start", "escape_chain"} <= {
        node.action_id for node in feature_subset.invocations
    }
    compiled = compiler.Compiler().compile(document)
    compiled_escapes = {
        invocation.mapping_id: invocation
        for invocation in compiled.invocations
        if invocation.function_kind == "escape"
    }
    assert compiled_escapes["escape_start"].output_features == ["escape_start_output"]
    assert compiled_escapes["escape_chain"].output_features == ["escape_chain_output"]
    assert compiled_escapes["escape_source"].input_features == []
    assert compiled_escapes["escape_source"].output_features == ["escape_source_output"]
    restored = compiler_plan.from_dict(json.loads(json.dumps(compiler_plan.to_dict(compiled))))
    assert restored == compiled
    assert restored.invocations == compiled.invocations


def test_feature_subset_retains_sink_roles_independent_of_function_kind(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    definitions = dict(functions.FUNCTION_KINDS)
    definitions[functions.ESCAPE] = dataclasses.replace(definitions[functions.ESCAPE], is_sink=True)
    monkeypatch.setattr(functions, "FUNCTION_KINDS", types.MappingProxyType(definitions))

    path = tmp_path / "sink_spec.json"
    path.write_text(json.dumps(_escape_spec_configuration()), encoding="utf-8")
    graph = compiler.InvocationGraph(spec.load_spec(path))
    subset = graph.subset(["escape_start_output"])

    assert "escape_unrelated" in {node.action_id for node in subset.invocations}


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
    assert all(
        escaped[function_id].output_features == []
        for function_id in (
            "returns_none",
            "returns_scalar",
            "returns_object",
            "returns_dataframe",
            "returns_unannotated",
        )
    )


def test_controlled_function_return_annotations_remain_validated() -> None:
    function = spec.load_spec(SPEC_PATH).functions["ratio"]

    with pytest.raises(ValueError, match="expected DataFrame or LazyFrame"):
        validation.validation_return_annotation(
            validation.CallableValidationContext(
                function,
                entrypoint.Signature(
                    parameters={},
                    return_annotation="int",
                ),
            )
        )


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
        ("collapse", "aggregate"),
        ("read", "read_pump_external_inputs"),
    }
    assert len(graph.invocations) == 18

    with pytest.raises(ValueError, match=r"Unknown output feature\(s\): missing"):
        graph.subset(["missing"])


def test_compiled_inputs_match_each_profile_mapping() -> None:
    document = spec.load_spec(SPEC_PATH)
    execution_plan = compiler.Compiler().compile(document)
    profiles = document.profiles

    assert len(profiles) > 1
    for invocation in execution_plan.invocations:
        operator = profiles[invocation.dataset_id].assembly[invocation.mapping_id]
        assert invocation.input_features == operator.input_features
        assert invocation.output_features == operator.output_features


def test_graph_subset_retains_profile_mapping_lookups() -> None:
    document = spec.load_spec(SPEC_PATH)
    graph = compiler.InvocationGraph(document)
    subset = graph.subset(["health_signal_normalized"])

    for node in subset.invocations:
        assert graph.profile_for(node) is document.profiles[node.dataset_id]
        assert subset.profile_for(node) is graph.profile_for(node)
        assert subset.action_for(node) is graph.action_for(node)
        assert {dependency.node_id for dependency in subset.dependencies(node)} == {
            dependency.node_id for dependency in graph.dependencies(node)
        }

    nested_subset = subset.subset(["health_signal_normalized"])
    assert {node.node_id for node in nested_subset.invocations} == {
        node.node_id for node in subset.invocations
    }
