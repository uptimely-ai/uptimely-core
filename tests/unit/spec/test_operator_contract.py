import json
import pathlib

import polars as pl
import pytest
from support import execution as execution_support

from uptimely import compiler, spec
from uptimely.engine.runtime import bindings as bindings_module
from uptimely.engine.runtime import state as state_module
from uptimely.spec import model as spec_model
from uptimely.spec.python import assembly, dimension, feature, merge, profile, ref

workflow_events: list[str] = []


def start_workflow() -> object:
    workflow_events.append("start")
    return object()


def finish_workflow() -> None:
    workflow_events.append("finish")


def finish_workflow_with_feature(identifier: str) -> None:
    workflow_events.append(identifier)


def test_feature_id_binding_orders_producer_before_consumer(
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    workflow_events.clear()
    document = spec.from_python(
        profiles=[
            profile.Profile(
                id="external",
                assembly=[
                    assembly.Operator(
                        id="start",
                        outputs=[feature.Feature(id="intermediate")],
                        compute=assembly.Bind(ref.function(start_workflow, returns="any")),
                    ),
                    assembly.Operator(
                        id="finish",
                        outputs=[feature.Feature(id="result")],
                        compute=assembly.Bind(
                            ref.function(finish_workflow_with_feature, returns="none"),
                            identifier=ref.feature("intermediate").id,
                        ),
                    ),
                ],
            )
        ]
    )
    assert document.profiles["external"].assembly["finish"].input_features == ["intermediate"]
    plan = compiler.Compiler().compile(document, features=["result"])
    result = engine_for_plan(plan, spec_definition=document).run()
    assert result.failures == {}
    assert workflow_events == ["start", "intermediate"]


def test_workflow_logical_features_order_execution_without_dataframes(
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    workflow_events.clear()
    document = spec.from_python(
        profiles=[
            profile.Profile(
                id="external",
                assembly=[
                    assembly.Operator(
                        id="start",
                        outputs=[feature.Feature(id="intermediate")],
                        compute=assembly.Bind(ref.function(start_workflow, returns="any")),
                    ),
                    assembly.Operator(
                        id="finish",
                        inputs=[ref.feature("intermediate")],
                        outputs=[feature.Feature(id="result")],
                        compute=assembly.Bind(ref.function(finish_workflow, returns="none")),
                    ),
                ],
            )
        ]
    )
    restored = spec.Spec.model_validate(document.model_dump())
    plan = compiler.Compiler().compile(restored, features=["result"])
    invocations = {item.semantics.operator_id: item for item in plan.invocations}
    stage_by_invocation = {
        invocation_id: index
        for index, stage in enumerate(plan.stages)
        for invocation_id in stage.invocation_ids
    }
    assert (
        stage_by_invocation[invocations["start"].id] < stage_by_invocation[invocations["finish"].id]
    )
    assert invocations["finish"].arguments == {}
    result = engine_for_plan(plan, spec_definition=restored).run()
    assert workflow_events == ["start", "finish"]
    assert result.failures == {}
    assert result.datasets == {}
    assert result.calculated_outputs is None


def test_feature_graph_contains_workflow_without_logical_features() -> None:
    document = spec.from_python(
        profiles=[
            profile.Profile(
                id="external",
                assembly=[
                    assembly.Operator(
                        id="run",
                        inputs=[],
                        outputs=[],
                        compute=assembly.Bind(ref.function(finish_workflow, returns="none")),
                    )
                ],
            )
        ]
    )
    graph = spec.FeatureGraph(document)
    assert any(node.reference.operator_id == "run" for node in graph.graph)


def read_values() -> pl.DataFrame:
    return pl.DataFrame({"id": [2, 1], "value": [20, 10]})


def read_lower_grain() -> pl.DataFrame:
    return pl.DataFrame({"id": [1, 2], "value": [10, 20]})


def read_target_grain(include_second: bool) -> pl.DataFrame:
    identifiers = [1, 2] if include_second else [1]
    return pl.DataFrame(
        {
            "id": identifiers,
            "region": ["north"] * len(identifiers),
            "target_value": identifiers,
        }
    )


def add_one(dataset: pl.DataFrame, output: str) -> pl.DataFrame:
    return dataset.with_columns((pl.col("value") + 1).alias(output))


def metadata_only(dataset: pl.DataFrame, identifier: str) -> pl.DataFrame:
    assert identifier == "result"
    return dataset.with_columns(pl.lit(7).alias("metadata"))


def write_ids(dataset: pl.DataFrame, column: str) -> None:
    assert dataset.sort(column)[column].to_list() == [1, 2]


def copy_values(dataset: pl.DataFrame, output: str) -> pl.DataFrame:
    return dataset.with_columns(pl.col("value").alias(output))


def dataset_identifier(
    dataset: pl.DataFrame,
    identifier: str,
    output: str,
) -> pl.DataFrame:
    return dataset.with_columns(pl.lit(identifier).alias(output))


def _spec() -> spec.Spec:
    identifier = dimension.Dimension(
        id="id",
        resolutions=[dimension.Resolution(id="id", key="id", type="integer")],
    )
    return spec.from_python(
        profiles=[
            profile.Profile(
                id="observations",
                grain=[identifier.resolution("id")],
                assembly=[
                    assembly.Operator(
                        id="read_values",
                        inputs=[],
                        outputs=[
                            feature.Feature(id="value", type="integer"),
                        ],
                        compute=assembly.Bind(
                            ref.function(read_values),
                        ),
                    ),
                    assembly.Operator(
                        id="result",
                        inputs=[ref.feature("value")],
                        outputs=[feature.Feature(id="result", type="integer")],
                        compute=assembly.Bind(
                            ref.function(add_one),
                            dataset=ref.profile().dataset,
                            output=ref.feature("result").id,
                        ),
                    ),
                    assembly.Operator(
                        id="metadata",
                        inputs=[ref.feature("value")],
                        outputs=[feature.Feature(id="metadata", type="integer")],
                        compute=assembly.Bind(
                            ref.function(metadata_only),
                            dataset=ref.profile().dataset,
                            identifier=ref.feature("result").id,
                        ),
                    ),
                ],
            )
        ]
    )


def test_explicit_inputs_drive_dependencies_not_identifier_arguments() -> None:
    spec_definition = _spec()
    profile_model = spec_definition.profiles["observations"]
    assert profile_model.assembly["metadata"].input_features == ["value"]
    assert profile_model.assembly["metadata"].output_features == ["metadata"]
    assert (
        profile_model.assembly["metadata"].compute.args["identifier"].root == "$features.result.id"
    )
    assert profile_model.assembly["result"].input_features == ["value"]

    computed = compiler.Compiler().compile(spec_definition, features=["result"])
    assert len(computed.invocations) == 2
    assert next(
        item for item in computed.invocations if item.semantics.dataframe_input_scope == "target"
    ).semantics.input_features == [
        "value",
    ]
    metadata = compiler.Compiler().compile(spec_definition, features=["metadata"])
    assert all("result" not in item.semantics.output_features for item in metadata.invocations)
    metadata_invocation = next(
        item for item in metadata.invocations if item.semantics.operator_id == "metadata"
    )
    read_values_invocation = next(
        item for item in metadata.invocations if item.semantics.operator_id == "read_values"
    )
    assert read_values_invocation.id in metadata.input_invocations[metadata_invocation.id]


def test_compute_can_merge_a_fragment_from_the_current_dataset(
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    document = _spec()
    document.profiles["observations"].assembly["result"].merge = merge.default().to_model()
    document = spec.Spec.model_validate(document.model_dump())
    compiled = compiler.Compiler().compile(document, features=["result"])
    computed = next(
        invocation
        for invocation in compiled.invocations
        if invocation.semantics.operator_id == "result" and invocation.semantics.role == "compute"
    )
    assert computed.semantics.result == "fragment"
    execution = engine_for_plan(compiled, spec_definition=document).run()
    assert execution.failures == {}
    assert execution.datasets["observations"].sort("id").select("id", "value", "result").rows() == [
        (1, 10, 11),
        (2, 20, 21),
    ]


def test_opaque_compute_orders_foreign_features_without_a_merge(
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    workflow_events.clear()
    document = _spec()
    publication = assembly.Operator(
        id="publish",
        inputs=["value"],
        compute=assembly.Bind(finish_workflow),
    )
    document.profiles["publication"] = spec_model.Profile(
        id="publication", assembly={"publish": publication.to_model()}
    )
    document.functions.root.update(publication.function_catalog().root)
    document = spec.Spec.model_validate(document.model_dump())
    compiled = compiler.Compiler().compile(document)
    publisher = next(
        item for item in compiled.invocations if item.semantics.operator_id == "publish"
    )
    producer = next(
        item for item in compiled.invocations if item.semantics.operator_id == "read_values"
    )
    stage_by_invocation = {
        invocation_id: index
        for index, stage in enumerate(compiled.stages)
        for invocation_id in stage.invocation_ids
    }
    assert stage_by_invocation[producer.id] < stage_by_invocation[publisher.id]
    execution = engine_for_plan(compiled, spec_definition=document).run()
    assert execution.failures == {}
    assert workflow_events == ["finish"]


def test_merge_binding_contract_is_validated_by_json_and_python_authoring(
    tmp_path: pathlib.Path,
) -> None:
    path = tmp_path / "spec.json"
    spec.write_document(_spec(), path)
    configuration = json.loads(path.read_text())
    configuration["profiles"]["observations"]["assembly"]["result"]["merge"] = {}
    path.write_text(json.dumps(configuration))
    with pytest.raises(ValueError, match="merge.function"):
        spec.load_spec(path)

    operator = assembly.Operator(
        id="vectorize",
        compute=assembly.Bind(
            ref.function(add_one),
            dataset=ref.dataset(),
            output="result",
        ),
        merge=assembly.Bind(
            ref.function(add_one),
            dataset=ref.dataset(),
            output="result",
        ),
    )
    with pytest.raises(ValueError, match="invalid dataframe arity"):
        operator.function_catalog()


@pytest.mark.parametrize(
    ("inputs", "message"),
    [
        (["$features.missing"], "unknown input feature"),
        (["$features.result"], "dependency cycle"),
        (["$features.value.id"], "must use"),
        (["$features.value", "$features.value"], "must not repeat"),
    ],
)
def test_invalid_input_contracts_are_rejected(
    tmp_path: pathlib.Path, inputs: list[str], message: str
) -> None:
    path = tmp_path / "spec.json"
    spec.write_document(_spec(), path)
    configuration = json.loads(path.read_text())
    configuration["profiles"]["observations"]["assembly"]["result"]["interface"]["inputs"] = inputs
    path.write_text(json.dumps(configuration))
    with pytest.raises(ValueError, match=message):
        spec.load_spec(path)


def test_selector_and_argument_type_must_agree(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "spec.json"
    spec.write_document(_spec(), path)
    configuration = json.loads(path.read_text())
    configuration["functions"]["add_one"]["args"]["output"]["type"] = "dataframe"
    configuration["functions"]["add_one"]["args"]["dataset"]["type"] = "string"
    path.write_text(json.dumps(configuration))
    with pytest.raises(ValueError, match="requires argument type dataframe"):
        spec.load_spec(path)


def test_nested_arguments_preserve_literals_and_resolve_dataframes() -> None:
    frame = read_values()
    state = state_module.RuntimeState(values={"$datasets.observations.read": frame})
    bindings = bindings_module.RuntimeBindings(state, {})
    assert bindings.resolve_value([None, 1]) == [None, 1]
    resolved = bindings.resolve_value({"frames": ["$datasets.observations.read"]})
    assert resolved["frames"][0] is frame
    with pytest.raises(ValueError, match="Return is unavailable"):
        bindings.resolve_value("$datasets.observations.missing")


@pytest.mark.parametrize("with_sink", [False, True])
def test_identifier_binding_needs_no_interface_or_feature_metadata(
    tmp_path: pathlib.Path, with_sink: bool, engine_for_plan: execution_support.EngineFactory
) -> None:
    path = tmp_path / "spec.json"
    spec.write_document(_spec(), path)
    configuration = json.loads(path.read_text())
    profile = configuration["profiles"]["observations"]
    assert "id" not in profile["features"]
    if with_sink:
        configuration["functions"]["write_ids"] = {
            "returns": "none",
            "entrypoint": f"{__name__}:write_ids",
            "args": {"dataset": {"type": "dataframe"}, "column": {"type": "string"}},
        }
        profile["assembly"]["write_ids"] = {
            "interface": {"inputs": ["$features.value"], "outputs": []},
            "compute": {
                "function": "write_ids",
                "args": {
                    "dataset": "$profiles.@.dataset",
                    "column": "$dimensions.id.resolutions.id.key",
                },
            },
        }
    path.write_text(json.dumps(configuration))
    spec_definition = spec.load_spec(path)
    compiled = compiler.Compiler().compile(spec_definition, features=["result"])
    execution = engine_for_plan(compiled, spec_definition=spec_definition).run()
    assert not execution.failures
    assert execution.datasets["observations"].sort("id")["result"].to_list() == [11, 21]


@pytest.mark.parametrize("dataframe", [False, True])
def test_dimensional_operator_schedules_only_its_foreign_dataframe_dependency(
    dataframe: bool,
) -> None:
    source_reference = ref.profile("source")
    identifier = dimension.Dimension(
        id="id",
        resolutions=[dimension.Resolution(id="id", key="id", type="integer")],
    )
    region = dimension.Dimension(
        id="region",
        resolutions=[dimension.Resolution(id="region", key="region", type="string")],
    )
    spec_definition = spec.from_python(
        profiles=[
            profile.Profile(
                id="source",
                grain=[identifier.resolution("id")],
                assembly=[
                    assembly.Operator(
                        id="read_lower_grain",
                        inputs=[],
                        outputs=[feature.Feature(id="value", type="integer")],
                        compute=assembly.Bind(
                            ref.function(read_lower_grain),
                        ),
                    )
                ],
            ),
            profile.Profile(
                id="target",
                grain=[
                    identifier.resolution("id"),
                    region.resolution("region"),
                ],
                assembly=[
                    assembly.Operator(
                        id="read_target_grain",
                        inputs=[],
                        outputs=[feature.Feature(id="target_value", type="integer")],
                        compute=assembly.Bind(
                            ref.function(read_target_grain),
                            include_second=dataframe,
                        ),
                    ),
                    assembly.Operator(
                        id="copied",
                        inputs=[ref.feature("value")],
                        outputs=[
                            feature.Feature(id="copied", type="integer" if dataframe else "string")
                        ],
                        compute=assembly.Bind(
                            ref.function(
                                copy_values if dataframe else dataset_identifier,
                            ),
                            **{
                                "dataset": source_reference.dataset,
                                "output": ref.feature("copied").id,
                                **({} if dataframe else {"identifier": source_reference.id}),
                            },
                        ),
                        merge=merge.default(),
                    ),
                ],
            ),
        ],
    )
    compiled = compiler.Compiler().compile(spec_definition, features=["copied"])
    assert len(compiled.invocations) == 3
    expand = next(
        item for item in compiled.invocations if item.semantics.fragment_dimensions == "subset"
    )
    source_merge = next(
        item
        for item in compiled.invocations
        if item.semantics.operator_id == "read_lower_grain" and item.semantics.result == "target"
    )
    assert source_merge.id in compiled.input_invocations[expand.id]
    assert expand.semantics.input_features == ["value"]
    assert expand.arguments["dataset"] == source_merge.returns
