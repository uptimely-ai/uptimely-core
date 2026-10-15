import json
import pathlib

import polars as pl
import pytest

from uptimely import compile, engine, spec
from uptimely.spec.python_spec import bind, dataset, dimension, feature, mapping, ref


def read_values() -> pl.DataFrame:
    return pl.DataFrame({"id": [2, 1], "value": [20, 10]})


def add_one(dataset: pl.DataFrame, output: str) -> pl.DataFrame:
    return dataset.with_columns((pl.col("value") + 1).alias(output))


def metadata_only(dataset: pl.DataFrame, identifier: str) -> pl.DataFrame:
    assert identifier == "result"
    return dataset.with_columns(pl.lit(7).alias("metadata"))


def write_ids(dataset: pl.DataFrame, column: str) -> None:
    assert dataset.sort(column)[column].to_list() == [1, 2]


def copy_values(dataset: pl.DataFrame, output: str) -> pl.DataFrame:
    return dataset.select("id", pl.col("value").alias(output))


def dataset_identifier(identifier: str, output: str) -> pl.DataFrame:
    return pl.DataFrame({"id": [1], output: [identifier]})


def _specification() -> spec.Specification:
    return spec.Specification.from_python(
        datasets=[
            dataset.Dataset(
                id="observations",
                mappings=[
                    mapping.Read(
                        bind=bind.bind(ref.function(read_values)),
                        outputs=[
                            feature.Feature(id="id", type="integer"),
                            feature.Feature(id="value", type="integer"),
                        ],
                    ),
                    mapping.Vectorize(
                        id="result",
                        inputs=[ref.feature("value")],
                        outputs=[feature.Feature(id="result", type="integer")],
                        bind=bind.bind(
                            ref.function(add_one),
                            dataset=ref.current_dataset().dataframe,
                            output=ref.feature("result").id,
                        ),
                    ),
                    mapping.Vectorize(
                        id="metadata",
                        outputs=[feature.Feature(id="metadata", type="integer")],
                        bind=bind.bind(
                            ref.function(metadata_only),
                            dataset=ref.current_dataset().dataframe,
                            identifier=ref.feature("result").id,
                        ),
                    ),
                ],
            )
        ],
        dimensions=[dimension.Dimension(id="id", type="integer")],
    )


def test_explicit_inputs_drive_dependencies_not_identifier_arguments() -> None:
    specification = _specification()
    computed = compile.Compiler(specification, features=["result"]).compile()
    assert len(computed.operations) == 2
    assert next(
        item for item in computed.operations if item.kind == "vectorize"
    ).input_features == [
        "value",
    ]
    metadata = compile.Compiler(specification, features=["metadata"]).compile()
    assert all("result" not in item.output_features for item in metadata.operations)
    execution = engine.Engine(metadata).execute()
    assert not execution.failures
    assert execution.datasets["entity", "observations"]["metadata"].to_list() == [7, 7]


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
    compiled = compile.Compiler(_specification(), features=["result"]).compile()

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
    execution = engine.Engine(compiled).execute()
    assert message in next(iter(execution.failures.values()))
    assert ("entity", "observations", "result") not in execution.calculated_outputs


def test_returned_row_order_does_not_control_alignment(monkeypatch: pytest.MonkeyPatch) -> None:
    compiled = compile.Compiler(_specification(), features=["result"]).compile()

    def reversed_result(dataset: pl.DataFrame, output: str) -> pl.DataFrame:
        return dataset.with_columns((pl.col("value") + 1).alias(output)).reverse()

    monkeypatch.setattr(f"{__name__}.add_one", reversed_result)
    execution = engine.Engine(compiled).execute()
    assert not execution.failures
    assert execution.datasets["entity", "observations"].sort("id").select(
        "id", "value", "result"
    ).rows() == [(1, 10, 11), (2, 20, 21)]


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
    _specification().to_json(path)
    configuration = json.loads(path.read_text())
    configuration["entities"]["entity"]["datasets"][0]["mappings"]["result"]["features"][
        "inputs"
    ] = inputs
    path.write_text(json.dumps(configuration))
    with pytest.raises(ValueError, match=message):
        spec.Specification.from_json(path)


def test_selector_and_argument_type_must_agree(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "spec.json"
    _specification().to_json(path)
    configuration = json.loads(path.read_text())
    configuration["functions"]["vectorize"]["add_one"]["args"]["dataset"]["type"] = "string"
    path.write_text(json.dumps(configuration))
    with pytest.raises(ValueError, match="requires argument type dataframe"):
        spec.Specification.from_json(path)


def test_nested_arguments_preserve_literals_and_resolve_dataframes() -> None:
    compiled = compile.Compiler(_specification()).compile()
    runtime = engine.Engine(compiled)
    frame = read_values()
    runtime._runtime_datasets = {("entity", "observations"): frame}
    assert runtime._resolve_value([None, 1], None, None) == [None, 1]
    resolved = runtime._resolve_value(
        {"frames": ["observations"]}, None, None, "object{str: array[dataframe]}"
    )
    assert resolved["frames"][0] is frame
    with pytest.raises(ValueError, match="dataframe is unavailable"):
        runtime._resolve_value("missing", None, None, "dataframe")


def test_implicit_dimensions_have_runtime_type_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    specification = _specification()
    source = next(iter(specification.entities["entity"].datasets[0].mappings.values()))
    source.features.outputs = ["$features.value"]
    compiled = compile.Compiler(specification, features=["result"]).compile()

    def wrong_dimension() -> pl.DataFrame:
        return read_values_original().with_columns(pl.col("id").cast(pl.String))

    read_values_original = read_values
    monkeypatch.setattr(f"{__name__}.read_values", wrong_dimension)
    execution = engine.Engine(compiled).execute()
    assert "Output column id has type String; expected integer" in next(
        iter(execution.failures.values())
    )
    assert not execution.datasets


@pytest.mark.parametrize("with_sink", [False, True])
def test_dimension_inputs_do_not_need_duplicate_feature_metadata(
    tmp_path: pathlib.Path, with_sink: bool
) -> None:
    path = tmp_path / "spec.json"
    _specification().to_json(path)
    configuration = json.loads(path.read_text())
    dataset = configuration["entities"]["entity"]["datasets"][0]
    del dataset["features"]["id"]
    dataset["mappings"]["read_values"]["features"]["outputs"] = ["$features.value"]
    dataset["mappings"]["result"]["features"]["inputs"].append("$features.id")
    if with_sink:
        configuration["functions"]["write"]["write_ids"] = {
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
    compiled = compile.Compiler(spec.Specification.from_json(path), features=["result"]).compile()
    execution = engine.Engine(compiled).execute()
    assert not execution.failures
    assert execution.datasets["entity", "observations"].sort("id")["result"].to_list() == [11, 21]


@pytest.mark.parametrize("dataframe", [False, True])
def test_dataset_selectors_only_schedule_actual_data_dependencies(dataframe: bool) -> None:
    source_reference = ref.dataset("source")
    specification = spec.Specification.from_python(
        dimensions=[dimension.Dimension(id="id", type="integer")],
        datasets=[
            dataset.Dataset(
                id="source",
                mappings=[
                    mapping.Read(
                        bind=bind.bind(ref.function(read_values)),
                        outputs=[
                            feature.Feature(id="id", type="integer"),
                            feature.Feature(id="value", type="integer"),
                        ],
                    )
                ],
            ),
            dataset.Dataset(
                id="target",
                mappings=[
                    mapping.Expand(
                        outputs=[
                            feature.Feature(id="copied", type="integer" if dataframe else "string")
                        ],
                        bind=(
                            bind.bind(
                                ref.function(copy_values),
                                dataset=source_reference.dataframe,
                                output=ref.feature("copied").id,
                            )
                            if dataframe
                            else bind.bind(
                                ref.function(dataset_identifier),
                                identifier=source_reference.id,
                                output=ref.feature("copied").id,
                            )
                        ),
                    )
                ],
            ),
        ],
    )
    compiled = compile.Compiler(specification, features=["copied"]).compile()
    assert len(compiled.operations) == (2 if dataframe else 1)
    execution = engine.Engine(compiled).execute()
    assert not execution.failures
    assert execution.datasets["entity", "target"].sort("id")["copied"].to_list() == (
        [10, 20] if dataframe else ["source"]
    )
