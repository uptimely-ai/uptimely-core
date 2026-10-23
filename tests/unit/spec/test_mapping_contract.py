import json
import pathlib

import polars as pl
import pytest
from conftest import engine_for_plan

from uptimely import compiler, spec
from uptimely.engine import bindings as bindings_module
from uptimely.engine import state as state_module
from uptimely.spec.python import dataset, dimension, entity, feature, mapping, ref


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


def copy_values(dataset: pl.DataFrame, other_dataset: pl.DataFrame, output: str) -> pl.DataFrame:
    return other_dataset.join(dataset.select("id", "value"), on="id").with_columns(
        pl.col("value").alias(output)
    )


def dataset_identifier(
    dataset: pl.DataFrame,
    other_dataset: pl.DataFrame,
    identifier: str,
    output: str,
) -> pl.DataFrame:
    return other_dataset.join(dataset.select("id"), on="id").with_columns(
        pl.lit(identifier).alias(output)
    )


def _spec() -> spec.Spec:
    return spec.from_python(
        datasets=[
            dataset.Dataset(
                id="observations",
                mappings={
                    "read_values": mapping.FunctionMapping(
                        inputs=[],
                        function=ref.function(read_values, operation="read"),
                        arguments={},
                        outputs=[
                            feature.Feature(name="id", type="integer"),
                            feature.Feature(name="value", type="integer"),
                        ],
                    ),
                    "result": mapping.FunctionMapping(
                        inputs=[ref.feature("value")],
                        function=ref.function(add_one, operation="vectorize"),
                        arguments={
                            "dataset": ref.current_dataset().dataframe,
                            "output": ref.feature("result").id,
                        },
                        outputs=[feature.Feature(name="result", type="integer")],
                    ),
                    "metadata": mapping.FunctionMapping(
                        inputs=[],
                        function=ref.function(metadata_only, operation="vectorize"),
                        arguments={
                            "dataset": ref.current_dataset().dataframe,
                            "identifier": ref.feature("result").id,
                        },
                        outputs=[feature.Feature(name="metadata", type="integer")],
                    ),
                },
            )
        ],
        dimensions=[dimension.Dimension(id="id", type="integer")],
    )


def test_explicit_inputs_drive_dependencies_not_identifier_arguments() -> None:
    spec_definition = _spec()
    computed = compiler.Compiler(spec_definition, features=["result"]).compile()
    assert len(computed.callables) == 2
    assert next(
        item for item in computed.callables if item.operation == "vectorize"
    ).input_features == [
        "value",
    ]
    metadata = compiler.Compiler(spec_definition, features=["metadata"]).compile()
    assert all("result" not in item.output_features for item in metadata.callables)
    execution = engine_for_plan(metadata, spec_definition=spec_definition).run()
    assert not execution.failures
    assert execution.datasets["observations"]["metadata"].to_list() == [7, 7]


@pytest.mark.parametrize(
    ("shape", "message"),
    [
        ("missing", "missing output columns: result"),
        ("keys", "missing dimension columns: id"),
        ("rows", "must preserve the dataset dimension keys"),
        ("type", "Output column result has type String; expected integer"),
        ("scalar", "must return a Polars DataFrame or LazyFrame"),
    ],
)
def test_dataframe_returns_are_validated(
    monkeypatch: pytest.MonkeyPatch, shape: str, message: str
) -> None:
    spec_definition = _spec()
    compiled = compiler.Compiler(spec_definition, features=["result"]).compile()

    def invalid(dataset: pl.DataFrame, output: str) -> object:
        if shape == "missing":
            return dataset
        if shape == "keys":
            return dataset.select(pl.col("value").alias(output))
        if shape == "rows":
            return dataset.head(1).with_columns(pl.lit(1).alias(output))
        if shape == "type":
            return dataset.with_columns(pl.lit("one").alias(output))
        return 1

    monkeypatch.setattr(f"{__name__}.add_one", invalid)
    execution = engine_for_plan(compiled, spec_definition=spec_definition).run()
    assert message in next(iter(execution.failures.values()))
    assert ("observations", "result") not in execution.calculated_outputs


def test_returned_row_order_does_not_control_alignment(monkeypatch: pytest.MonkeyPatch) -> None:
    spec_definition = _spec()
    compiled = compiler.Compiler(spec_definition, features=["result"]).compile()

    def reversed_result(dataset: pl.DataFrame, output: str) -> pl.DataFrame:
        return dataset.with_columns((pl.col("value") + 1).alias(output)).reverse()

    monkeypatch.setattr(f"{__name__}.add_one", reversed_result)
    execution = engine_for_plan(compiled, spec_definition=spec_definition).run()
    assert not execution.failures
    assert execution.datasets["observations"].sort("id").select("id", "value", "result").rows() == [
        (1, 10, 11),
        (2, 20, 21),
    ]


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
    configuration["entities"]["entity"]["datasets"]["observations"]["mappings"]["result"][
        "features"
    ]["inputs"] = inputs
    path.write_text(json.dumps(configuration))
    with pytest.raises(ValueError, match=message):
        spec.load_spec(path)


def test_selector_and_argument_type_must_agree(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "spec.json"
    spec.write_document(_spec(), path)
    configuration = json.loads(path.read_text())
    configuration["functions"]["add_one"]["args"]["dataset"]["type"] = "string"
    path.write_text(json.dumps(configuration))
    with pytest.raises(ValueError, match="requires argument type dataframe"):
        spec.load_spec(path)


def test_nested_arguments_preserve_literals_and_resolve_dataframes() -> None:
    spec_definition = _spec()
    frame = read_values()
    state = state_module.RuntimeState(datasets={"observations": frame})
    bindings = bindings_module.RuntimeBindings(spec_definition, state, {})
    assert bindings.resolve_value([None, 1]) == [None, 1]
    resolved = bindings.resolve_value({"frames": ["observations"]}, "object{str: array[dataframe]}")
    assert resolved["frames"][0] is frame
    with pytest.raises(ValueError, match="dataframe is unavailable"):
        bindings.resolve_value("missing", "dataframe")


def test_implicit_dimensions_have_runtime_type_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec_definition = _spec()
    source = next(
        iter(spec_definition.entities["entity"].datasets["observations"].mappings.values())
    )
    source.features.outputs = ["$features.value"]
    compiled = compiler.Compiler(spec_definition, features=["result"]).compile()

    def wrong_dimension() -> pl.DataFrame:
        return read_values_original().with_columns(pl.col("id").cast(pl.String))

    read_values_original = read_values
    monkeypatch.setattr(f"{__name__}.read_values", wrong_dimension)
    execution = engine_for_plan(compiled, spec_definition=spec_definition).run()
    assert "Output column id has type String; expected integer" in next(
        iter(execution.failures.values())
    )
    assert not execution.datasets


@pytest.mark.parametrize("with_sink", [False, True])
def test_dimension_inputs_do_not_need_duplicate_feature_metadata(
    tmp_path: pathlib.Path, with_sink: bool
) -> None:
    path = tmp_path / "spec.json"
    spec.write_document(_spec(), path)
    configuration = json.loads(path.read_text())
    dataset = configuration["entities"]["entity"]["datasets"]["observations"]
    del dataset["features"]["id"]
    dataset["mappings"]["read_values"]["features"]["outputs"] = ["$features.value"]
    dataset["mappings"]["result"]["features"]["inputs"].append("$features.id")
    if with_sink:
        configuration["functions"]["write_ids"] = {
            "operation": "write",
            "returns": "none",
            "entrypoint": f"{__name__}:write_ids",
            "args": {"dataset": {"type": "dataframe"}, "column": {"type": "string"}},
        }
        dataset["mappings"]["write_ids"] = {
            "features": {"inputs": ["$features.id"], "outputs": []},
            "binding": {
                "function": "write_ids",
                "args": {"dataset": "$datasets.@.dataframe", "column": "$dimensions.id.id"},
            },
        }
    path.write_text(json.dumps(configuration))
    spec_definition = spec.load_spec(path)
    compiled = compiler.Compiler(spec_definition, features=["result"]).compile()
    execution = engine_for_plan(compiled, spec_definition=spec_definition).run()
    assert not execution.failures
    assert execution.datasets["observations"].sort("id")["result"].to_list() == [11, 21]


@pytest.mark.parametrize("dataframe", [False, True])
def test_dataset_selectors_only_schedule_actual_data_dependencies(dataframe: bool) -> None:
    source_reference = ref.dataset("source")
    spec_definition = spec.from_python(
        dimensions=[
            dimension.Dimension(id="id", type="integer"),
            dimension.Dimension(id="region", type="string"),
        ],
        entities=[
            entity.Entity(
                id="source_entity",
                name="Source",
                dimensions=[dimension.Dimension(id="id", type="integer")],
                datasets=[
                    dataset.Dataset(
                        id="source",
                        mappings={
                            "read_lower_grain": mapping.FunctionMapping(
                                inputs=[],
                                function=ref.function(read_lower_grain, operation="read"),
                                arguments={},
                                outputs=[feature.Feature(name="value", type="integer")],
                            )
                        },
                    )
                ],
            ),
            entity.Entity(
                id="target_entity",
                name="Target",
                dimensions=[
                    dimension.Dimension(id="id", type="integer"),
                    dimension.Dimension(id="region", type="string"),
                ],
                datasets=[
                    dataset.Dataset(
                        id="target",
                        mappings={
                            "read_target_grain": mapping.FunctionMapping(
                                inputs=[],
                                function=ref.function(read_target_grain, operation="read"),
                                arguments={"include_second": dataframe},
                                outputs=[feature.Feature(name="target_value", type="integer")],
                            ),
                            "copied": mapping.FunctionMapping(
                                inputs=[ref.feature("value")],
                                outputs=[
                                    feature.Feature(
                                        name="copied", type="integer" if dataframe else "string"
                                    )
                                ],
                                function=ref.function(
                                    copy_values if dataframe else dataset_identifier,
                                    operation="expand",
                                ),
                                arguments={
                                    "dataset": source_reference.dataframe,
                                    "other_dataset": ref.current_dataset().dataframe,
                                    "output": ref.feature("copied").id,
                                    **({} if dataframe else {"identifier": source_reference.id}),
                                },
                            ),
                        },
                    )
                ],
            ),
        ],
    )
    compiled = compiler.Compiler(spec_definition, features=["copied"]).compile()
    assert len(compiled.callables) == 3
    execution = engine_for_plan(compiled, spec_definition=spec_definition).run()
    assert not execution.failures
    assert execution.datasets["target"].sort("id")["copied"].to_list() == (
        [10, 20] if dataframe else ["source"]
    )
