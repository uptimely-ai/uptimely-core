import json
from pathlib import Path

from uptimely.spec import Specification
from uptimely.spec.python_spec import bind, dataset, feature, fragment, ref
from uptimely.spec.python_spec.bind import _argument_definition

SPEC_PATH = Path("examples/example_1/generated/spec/spec.json")


def test_argument_definition_supports_recursive_compact_types() -> None:
    assert _argument_definition({"value": 1.0}) == {"type": "object{str: float}"}
    assert _argument_definition({"value": {"nested": 1.0}}) == {
        "type": "object{str: object{str: float}}"
    }
    assert _argument_definition({"dimensions": [ref.dimension("plant")]}) == {
        "type": "object{str: array[string]}"
    }
    assert _argument_definition({"value": 1.0, "other": "text"}) == {"type": "object"}


def test_function_catalog_uses_vectorize_category() -> None:
    specification = Specification.from_json(SPEC_PATH)

    categories = set(specification.functions.model_dump(exclude_none=True))
    assert "vectorize" in categories


def test_example_manifest_parses_complete_specification() -> None:
    specification = Specification.from_json(SPEC_PATH)
    specification_from_directory = Specification.from_json(SPEC_PATH.parent)

    assert not hasattr(specification, "environments")
    assert specification_from_directory.path.endswith("spec.json")
    assert not hasattr(specification, "orchestration")
    assert not hasattr(specification, "engine")
    assert not hasattr(specification, "storage")
    assert specification.dimensions["pump"].parent == "production_line"
    assert set(specification.entities) == {"pump_telemetry", "pump"}
    assert specification.entities["pump_telemetry"].dimensions == [
        "plant",
        "production_line",
        "pump",
        "timestamp",
    ]
    assert isinstance(specification, Specification)
    assert set(specification.functions.model_dump(exclude_none=True)) == {
        "read",
        "write",
        "vectorize",
        "aggregate",
        "collapse",
        "expand",
        "conform",
    }
    assert set(specification.functions.vectorize) - {"maximum"} == {
        function.id for function in specification.resolved_functions
    }
    assert len(specification.resolved_functions) == 8

    pump_dataset = specification.entities["pump"].datasets[0]
    aggregate = pump_dataset.collapse["bearing_temperature_by_pump"]
    assert aggregate.binding.function == "aggregate_by_dimension"
    assert "bearing_temperature_max" in aggregate.features


def test_spec_from_entities_python_api(tmp_path: Path) -> None:
    from examples.example_2.spec.spec import dimensions, entity_

    specification = Specification.from_python(
        entities=[entity_],
        dimensions=dimensions,
    )

    assert specification.entities["example_2"].datasets[0].id == "my_beautiful_dataset"
    assert specification.functions.read


def test_spec_from_python_models_and_json_export(tmp_path: Path) -> None:
    from examples.example_2.spec.spec import dataset_, dimensions

    functions = dataset_.function_catalog()

    specification = Specification.from_python(
        datasets=[dataset_],
        functions=functions,
        name="example_2",
        dimensions=dimensions,
    )
    output_path = tmp_path / "spec.json"
    specification.to_json(output_path)

    assert specification.entities
    assert specification.entities["example_2"].datasets[0].id
    assert output_path.exists()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    dataset_payload = payload["entities"]["example_2"]["datasets"][0]
    assert payload["version"] == "0.1.0"
    assert set(payload["functions"]) == {"read", "write", "vectorize", "aggregate"}
    assert payload["functions"]["read"]["read"]["entrypoint"].endswith(":read_data")
    assert payload["functions"]["write"]["write"]["entrypoint"].endswith(":write_data")
    assert payload["functions"]["vectorize"]["sum_features"]["entrypoint"].endswith(":sum_features")
    assert set(dataset_payload) == {
        "id",
        "description",
        "row_scope",
        "read",
        "conform",
        "expand",
        "collapse",
        "vectorize",
        "write",
    }
    assert dataset_payload["description"]
    assert dataset_payload["read"]["read"]["binding"]["function"] == "read"
    assert dataset_payload["write"]["write"]["binding"]["args"]["df"] == "$datasets.@"
    assert dataset_payload["vectorize"]["column_3"]["binding"]["args"] == {
        "left_feature": "$features.input_1",
        "right_feature": "$features.input_2",
        "output": "$features.column_3",
    }
    assert dataset_payload["vectorize"]["column_3"]["unit"] is None
    assert "type" not in dataset_payload["vectorize"]["column_3"]
    assert "entrypoint" not in dataset_payload["vectorize"]["column_3"]


def test_sources_and_transforms_python_spec(tmp_path: Path) -> None:
    from examples.example_2.functions import functions

    source_op = fragment.Read(
        id="read",
        bind=bind.bind(functions.read_data),
        features=[feature.Raw(id="input_1", description="Input feature: input_1")],
    )

    transform_op = fragment.Expand(
        id="expand_data",
        bind=bind.bind(functions.read_data),
        features=[feature.Raw(id="input_2", description="Input feature: input_2")],
    )

    collapse_op = fragment.Collapse(
        id="collapse_data",
        bind=bind.bind(
            functions.read_data,
            aggregations={
                "collapsed_feature": feature.aggregation(
                    functions.tag_first_item,
                    id_column=ref.feature("input_1"),
                )
            },
        ),
        features=[
            feature.Raw(
                id="collapsed_feature",
                description="Feature generated while collapsing data",
            )
        ],
    )

    dataset_obj = dataset.Dataset(
        id="transformed_dataset",
        read=[source_op],
        expand=[transform_op],
        collapse=[collapse_op],
    )

    functions_cat = dataset_obj.function_catalog()
    spec = Specification.from_python(
        datasets=[dataset_obj],
        functions=functions_cat,
        name="transforms_test",
    )

    out_json = tmp_path / "spec.json"
    spec.to_json(out_json)

    ds_model = spec.entities["transforms_test"].datasets[0]
    assert "read" in ds_model.read
    assert "expand_data" in ds_model.expand
    assert "collapse_data" in ds_model.collapse
    assert "input_1" in ds_model.all_features
    assert "input_2" in ds_model.all_features
    aggregation_binding = ds_model.collapse["collapse_data"].binding.args["aggregations"][
        "collapsed_feature"
    ]
    assert aggregation_binding == {
        "function": "tag_first_item",
        "args": {"id_column": "$features.input_1"},
    }
    assert "tag_first_item" in spec.functions.aggregate
