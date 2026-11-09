import dataclasses
import json
import pathlib
import types

import pytest
from support import examples as example_support

from uptimely import compiler, entrypoint, spec
from uptimely import plan as compiler_plan
from uptimely.compiler import compiler as compiler_module
from uptimely.compiler import validation
from uptimely.spec import model as spec_model
from uptimely.spec import operator_kinds as functions

SPEC_PATH = example_support.EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json"
pytestmark = pytest.mark.usefixtures("example_projects")


def _add_escape_mapping(
    configuration: dict,
    operator_id: str,
    function_id: str,
    input_features: list[str],
    entrypoint: str,
    output_features: list[str] | None = None,
) -> None:
    """Add one escape operator with logical feature dependencies."""
    configuration["functions"][function_id] = {
        "returns": "any",
        "entrypoint": entrypoint,
        "args": {},
    }
    configuration["profiles"]["pump_telemetry"]["assembly"][operator_id] = {
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
    assert {
        invocation["id"]: invocation["return_type"] for invocation in actual["invocations"]
    } == {invocation["id"]: invocation["return_type"] for invocation in expected["invocations"]}
    assert all(invocation["package"] is not None for invocation in actual["invocations"])
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
            "source_keys": "$profiles.pump.grain.ids",
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
    expected_source = definition.grain_keys_by_profile["pump"]

    assert invocation.arguments["keys"] == expected
    assert invocation.arguments["source_keys"] == expected_source
    portable = compiler_plan.to_dict(plan)
    portable_invocation = next(
        item for item in portable["invocations"] if item["function_id"] == "read_pump_telemetry"
    )
    assert portable_invocation["arguments"]["keys"] == expected
    assert portable_invocation["arguments"]["source_keys"] == expected_source


def test_collapse_feature_placeholder_uses_declared_output(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    operator = configuration["profiles"]["pump"]["assembly"]["bearing_temperature_by_pump"]
    operator["compute"]["args"]["output"] = "$features.@.id"
    path = tmp_path / "collapse_feature_placeholder.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")

    definition = spec.load_spec(path)
    plan = compiler.Compiler().compile(definition)
    invocation = next(
        item
        for item in plan.invocations
        if item.operator_id == "bearing_temperature_by_pump" and item.operator_kind == "collapse"
    )

    assert "bearing_temperature_max" in invocation.output_features
    assert invocation.arguments["output"] == "bearing_temperature_max"


def test_compiler_keeps_reused_function_mappings_as_distinct_invocations() -> None:
    plan = compiler.Compiler().compile(spec.load_spec(SPEC_PATH))
    invocations = [
        invocation for invocation in plan.invocations if invocation.function_id == "extract_field"
    ]

    assert {feature for invocation in invocations for feature in invocation.output_features} == {
        "recommended_discharge_pressure",
        "energy_cost_score",
        "converged",
    }
    assert len(invocations) == 3
    assert len({invocation.id for invocation in invocations}) == 3
    direct_invocations = [
        invocation
        for invocation in plan.invocations
        if invocation.function_id == "LazyFrame.with_columns"
    ]
    assert len(direct_invocations) == 1
    assert direct_invocations[0].operator_id == "recommended_flow_rate"
    assert direct_invocations[0].output_features == ["recommended_flow_rate"]
    assert direct_invocations[0].arguments["recommended_flow_rate"] == "flow_rate"


def test_compact_invocation_ids_are_stable_across_recompilation_and_selection() -> None:
    document = spec.load_spec(SPEC_PATH)
    builder = compiler.Compiler()
    full_plan = builder.compile(document)
    repeated_plan = builder.compile(document)
    selected_plan = builder.compile(document, features=["health_signal_normalized"])
    full_by_binding = {
        (item.operator_kind, item.function_id, item.profile_id, item.operator_id): item.id
        for item in full_plan.invocations
    }

    assert {
        (item.operator_kind, item.function_id, item.profile_id, item.operator_id): item.id
        for item in repeated_plan.invocations
    } == full_by_binding
    assert selected_plan.invocations
    for item in selected_plan.invocations:
        assert (
            item.id
            == full_by_binding[
                (item.operator_kind, item.function_id, item.profile_id, item.operator_id)
            ]
        )
        assert len(item.id) <= 36
        assert item.id.count("--") == 1
    assert compiler_plan.from_dict(compiler_plan.to_dict(selected_plan)) == selected_plan


def test_existing_invocation_ids_survive_unrelated_additions_and_reordering() -> None:
    document = spec.load_spec(SPEC_PATH)
    builder = compiler.Compiler()
    original = builder.compile(document)
    configuration = document.model_dump(mode="json")
    _add_escape_mapping(
        configuration,
        "unrelated_escape",
        "unrelated_escape",
        [],
        "examples.pump_analytics.functions.external_workflow:process_pump_external_workflow",
    )
    configuration["functions"]["unrelated_escape"]["validate_signature"] = False
    configuration["profiles"] = dict(reversed(configuration["profiles"].items()))
    for profile in configuration["profiles"].values():
        profile["assembly"] = dict(reversed(profile["assembly"].items()))
    expanded = builder.compile(spec.Spec.model_validate(configuration))

    assert {item.id for item in original.invocations} < {item.id for item in expanded.invocations}
    assert len(expanded.invocations) == len(original.invocations) + 1


def test_compiler_emits_conform_invocation_with_its_dataset_dependency() -> None:
    definition = spec.load_spec(SPEC_PATH)
    pump_profile = definition.profiles["pump"]
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
                "source": "$profiles.auxiliary_dataset.dataset",
            },
        ),
        interface=spec_model.Interface(
            inputs=["$features.auxiliary_value"],
            outputs=["$features.conformed_auxiliary"],
        ),
    )
    definition.functions.root["conform_auxiliary"] = spec_model.FunctionTemplate(
        id="conform_auxiliary",
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
        invocation for invocation in plan.invocations if invocation.operator_kind == "conform"
    )
    source = next(
        invocation
        for invocation in plan.invocations
        if invocation.operator_id == "read_auxiliary" and invocation.result == "target"
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
        if invocation.operator_kind == "vectorize"
        for feature in invocation.output_features
    ] == [
        "health_signal_normalized",
    ]
    assert {invocation.operator_kind for invocation in plan.invocations} == {
        "read",
        "collapse",
        "vectorize",
    }
    assert {
        feature
        for invocation in plan.invocations
        if invocation.operator_kind == "vectorize"
        for feature in invocation.output_features
    } == {
        "health_signal_normalized",
    }

    with pytest.raises(ValueError, match=r"Unknown output feature\(s\): missing"):
        compiler.Compiler().compile(spec.load_spec(SPEC_PATH), features=["missing"])


def test_compiler_emits_one_operation_for_multi_output_mapping(tmp_path: pathlib.Path) -> None:
    spec_definition = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    dataset = spec_definition["profiles"]["pump"]
    operator = dataset["assembly"]["health_signal_normalized"]
    operator["interface"]["outputs"].append("$features.health_signal_secondary")
    dataset["features"]["health_signal_secondary"] = {"type": "float"}
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec_definition), encoding="utf-8")

    plan = compiler.Compiler().compile(
        spec.load_spec(spec_path), features=["health_signal_normalized"]
    )
    vectorize_invocations = [
        invocation for invocation in plan.invocations if invocation.operator_kind == "vectorize"
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
    compiled = compiler.Compiler().compile(document)
    by_operator = {invocation.operator_id: invocation for invocation in compiled.invocations}
    by_id = compiled.invocations_by_id

    assert {
        invocation.operator_id
        for invocation in compiled.invocations
        if invocation.operator_kind == "escape"
    } == {
        "escape_start",
        "escape_chain",
        "escape_unrelated",
        "escape_source",
        "process_pump_external_workflow",
    }
    assert {
        by_id[dependency_id].operator_id
        for dependency_id in by_operator["escape_start"].dependency_ids
    } == {"read_pump_telemetry"}
    assert {
        by_id[dependency_id].operator_id
        for dependency_id in by_operator["escape_chain"].dependency_ids
    } == {"escape_start"}

    assert {
        by_id[dependency_id].operator_id
        for dependency_id in by_operator["escape_unrelated"].dependency_ids
    } == {"read_pump_telemetry"}
    assert by_operator["escape_source"].dependency_ids == []
    assert by_operator["escape_start"].output_features == ["escape_start_output"]
    assert by_operator["escape_chain"].output_features == ["escape_chain_output"]
    assert by_operator["escape_source"].input_features == []
    assert by_operator["escape_source"].output_features == ["escape_source_output"]
    assert {
        "escape_chain_output",
        "escape_source_output",
    } <= spec.FeatureGraph(document).feature_names
    feature_subset = compiler.Compiler().compile(document, features=["escape_chain_output"])
    assert {"escape_start", "escape_chain"} <= {
        invocation.operator_id for invocation in feature_subset.invocations
    }
    compiled_escapes = {
        invocation.operator_id: invocation
        for invocation in compiled.invocations
        if invocation.operator_kind == "escape"
    }
    assert compiled_escapes["escape_start"].output_features == ["escape_start_output"]
    assert compiled_escapes["escape_chain"].output_features == ["escape_chain_output"]
    assert compiled_escapes["escape_source"].input_features == []
    assert compiled_escapes["escape_source"].output_features == ["escape_source_output"]
    restored = compiler_plan.from_dict(json.loads(json.dumps(compiler_plan.to_dict(compiled))))
    assert restored == compiled
    assert restored.invocations == compiled.invocations


def test_feature_subset_retains_sink_roles_independent_of_operator_kind(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    definitions = dict(functions.OPERATOR_KINDS)
    definitions[functions.ESCAPE] = dataclasses.replace(definitions[functions.ESCAPE], is_sink=True)
    monkeypatch.setattr(functions, "OPERATOR_KINDS", types.MappingProxyType(definitions))

    path = tmp_path / "sink_spec.json"
    path.write_text(json.dumps(_escape_spec_configuration()), encoding="utf-8")
    subset = compiler.Compiler().compile(spec.load_spec(path), features=["escape_start_output"])

    assert "escape_unrelated" in {invocation.operator_id for invocation in subset.invocations}


def test_feature_index_uses_operator_kind_output_contract(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "feature_contract_spec.json"
    path.write_text(json.dumps(_escape_spec_configuration()), encoding="utf-8")
    document = spec.load_spec(path)
    definitions = dict(functions.OPERATOR_KINDS)
    definitions[functions.ESCAPE] = dataclasses.replace(
        definitions[functions.ESCAPE], produces_features=False
    )
    monkeypatch.setattr(functions, "OPERATOR_KINDS", types.MappingProxyType(definitions))
    monkeypatch.setattr(compiler_module.spec_validation, "validate_spec", lambda _spec: None)

    plan = compiler.Compiler().compile(document)
    chain = next(item for item in plan.invocations if item.operator_id == "escape_chain")
    assert chain.dependency_ids == []
    with pytest.raises(ValueError, match=r"Unknown output feature\(s\): escape_start_output"):
        compiler.Compiler().compile(document, features=["escape_start_output"])


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
        function_id: invocation.return_type
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


def test_compiler_feature_subset_contains_requested_output_and_ancestors() -> None:
    document = spec.load_spec(SPEC_PATH)
    subset = compiler.Compiler().compile(document, features=["health_signal_normalized"])
    normalized = next(
        invocation
        for invocation in subset.invocations
        if "health_signal_normalized" in invocation.output_features
    )

    assert normalized.output_features == ["health_signal_normalized"]
    assert {
        (
            subset.invocations_by_id[dependency_id].role,
            subset.invocations_by_id[dependency_id].function_id,
        )
        for dependency_id in normalized.dependency_ids
    } == {("merge", "merge_by_grain")}
    assert {
        invocation.operator_id
        for invocation in subset.invocations
        if invocation.operator_kind == "collapse"
    } == {"bearing_temperature_by_pump"}

    with pytest.raises(ValueError, match=r"Unknown output feature\(s\): missing"):
        compiler.Compiler().compile(document, features=["missing"])
    grain_key_output = next(
        feature for feature in document.grain_key_ids if feature in document.feature_producers
    )
    with pytest.raises(
        ValueError,
        match=rf"Unknown output feature\(s\): {grain_key_output}",
    ):
        compiler.Compiler().compile(document, features=[grain_key_output])


def test_compiled_inputs_match_each_profile_mapping() -> None:
    document = spec.load_spec(SPEC_PATH)
    execution_plan = compiler.Compiler().compile(document)
    profiles = document.profiles

    assert len(profiles) > 1
    for invocation in execution_plan.invocations:
        operator = profiles[invocation.profile_id].assembly[invocation.operator_id]
        if invocation.role == "merge":
            assert invocation.input_features == []
            assert invocation.output_features == []
            continue
        assert invocation.input_features == operator.input_features
        assert invocation.output_features == operator.output_features


def test_compiler_feature_subset_uses_source_profile_and_operator_declarations() -> None:
    document = spec.load_spec(SPEC_PATH)
    subset = compiler.Compiler().compile(document, features=["health_signal_normalized"])

    for invocation in subset.invocations:
        operator = document.profiles[invocation.profile_id].assembly[invocation.operator_id]
        if invocation.role == "merge":
            assert invocation.input_features == []
            assert invocation.output_features == []
            continue
        assert invocation.input_features == operator.input_features
        assert invocation.output_features == operator.output_features
