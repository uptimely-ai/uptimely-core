import json
import pathlib

import polars as pl
from conftest import EXAMPLES_ROOT
from examples.pump_analytics.functions import analytics
from examples.pump_analytics.spec import dimension as pump_dimensions
from examples.pump_analytics.spec import entity as pump_entities
from examples.pump_analytics.spec import spec as pump_telemetry_spec
from examples.simple_analytics.functions import functions
from examples.simple_analytics.spec import spec as simple_analytics_module

from uptimely import spec
from uptimely.spec import python as python_spec
from uptimely.spec.python import bind

SPEC_PATH = EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json"


def test_maximum_executes_independently() -> None:
    frame = pl.LazyFrame({"pump": ["a", "a"], "temperature": [10.0, 20.0]})

    result = analytics.maximum(frame, "temperature", ["pump"], "maximum")

    assert isinstance(result, pl.LazyFrame)
    assert result.collect().to_dicts() == [{"pump": "a", "maximum": 20.0}]
    assert frame.collect().to_dicts() == [
        {"pump": "a", "temperature": 10.0},
        {"pump": "a", "temperature": 20.0},
    ]


def test_pump_dimensions_are_declared_in_spec_order() -> None:
    expected = [
        pump_dimensions.PLANT,
        pump_dimensions.PRODUCTION_LINE,
        pump_dimensions.PUMP,
        pump_dimensions.TIMESTAMP,
    ]

    assert pump_telemetry_spec.python_spec.dimensions == expected
    assert pump_dimensions.PRODUCTION_LINE.parent == pump_dimensions.PLANT.id
    assert pump_dimensions.PUMP.parent == pump_dimensions.PRODUCTION_LINE.id


def test_pump_entities_are_declared_in_spec_order() -> None:
    expected = [pump_entities.PUMP_TELEMETRY, pump_entities.PUMP]

    assert pump_entities.entities == expected
    assert [entity.id for entity in pump_telemetry_spec.python_spec.entities] == [
        "pump_telemetry",
        "pump",
    ]
    assert pump_entities.PUMP_TELEMETRY.dimensions == pump_telemetry_spec.python_spec.dimensions
    assert pump_entities.PUMP.dimensions == [
        pump_dimensions.PLANT,
        pump_dimensions.PRODUCTION_LINE,
        pump_dimensions.PUMP,
    ]
    assert list(pump_telemetry_spec.python_spec.datasets) == expected
    assert [
        dataset.id
        for entity in pump_telemetry_spec.python_spec.entities
        for dataset in entity.datasets
    ] == ["pump_telemetry_dataset", "pump_dataset"]


def test_argument_definition_supports_recursive_compact_types() -> None:
    assert bind._argument_definition({"value": 1.0}) == {"type": "object{str: float}"}
    assert bind._argument_definition({"value": {"nested": 1.0}}) == {
        "type": "object{str: object{str: float}}"
    }
    assert bind._argument_definition({"dimensions": [python_spec.ref.dimension("plant")]}) == {
        "type": "object{str: array[string]}"
    }
    assert bind._argument_definition({"value": 1.0, "other": "text"}) == {"type": "object"}


def test_function_catalog_functions_declare_operations() -> None:
    spec_definition = spec.load_spec(SPEC_PATH)

    operations = {function.operation for function in spec_definition.functions.root.values()}
    assert "vectorize" in operations


def test_example_manifest_parses_complete_spec() -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    spec_from_directory = spec.load_spec(SPEC_PATH.parent)

    assert spec_from_directory == spec_definition
    assert spec_definition.dimensions["pump"].parent == "production_line"
    assert set(spec_definition.entities) == {"pump_telemetry", "pump"}
    assert spec_definition.entities["pump_telemetry"].dimension_ids == [
        "plant",
        "production_line",
        "pump",
        "timestamp",
    ]
    assert spec_definition.entities["pump_telemetry"].dimensions == [
        spec_definition.dimensions[identifier]
        for identifier in ("plant", "production_line", "pump", "timestamp")
    ]
    assert isinstance(spec_definition, spec.Spec)
    assert spec_definition.source.name == "python_api"
    assert spec_definition.source.generated is True
    assert {function.operation for function in spec_definition.functions.root.values()} == {
        "read",
        "write",
        "vectorize",
        "collapse",
    }
    assert "maximum" not in spec_definition.functions.by_operation("vectorize")
    assert len(spec_definition.functions.by_operation("vectorize")) == 7

    pump_dataset = spec_definition.entities["pump"].datasets["pump_dataset"]
    collapse = pump_dataset.mappings["bearing_temperature_by_pump"]
    assert not hasattr(collapse, "source")
    assert collapse.binding.function == "maximum"
    assert "bearing_temperature_max" in collapse.output_features


def test_spec_from_entities_python_api(tmp_path: pathlib.Path) -> None:
    spec_definition = spec.from_python(
        entities=simple_analytics_module.python_spec.entities,
        dimensions=simple_analytics_module.python_spec.dimensions,
        name=simple_analytics_module.python_spec.name,
    )

    assert (
        spec_definition.entities["simple_analytics"].datasets["my_beautiful_dataset"].id
        == "my_beautiful_dataset"
    )
    assert spec_definition.name == "Simple analytics"
    assert spec_definition.source.name == "python_api"
    assert spec_definition.source.generated is True
    assert spec_definition.functions.by_operation("read")


def test_example_timestamp_order_matches_python_declaration() -> None:
    authored = spec.from_python(
        entities=pump_telemetry_spec.python_spec.entities,
        dimensions=pump_telemetry_spec.python_spec.dimensions,
    )
    exported = spec.load_spec(SPEC_PATH)
    expected = [{"dimension": "$dimensions.timestamp", "direction": "asc"}]
    for spec_definition in (authored, exported):
        assert [
            key.model_dump()
            for key in spec_definition.entities["pump_telemetry"]
            .datasets["pump_telemetry_dataset"]
            .order
        ] == expected
        assert spec_definition.entities["pump"].datasets["pump_dataset"].order == []


def test_spec_from_python_models_and_json_export(tmp_path: pathlib.Path) -> None:
    spec_definition = spec.from_python(
        datasets=[simple_analytics_module.dataset_],
        functions=simple_analytics_module.dataset_.function_catalog(),
        name="simple_analytics",
        dimensions=simple_analytics_module.python_spec.dimensions,
    )
    output_path = tmp_path / "spec.json"
    spec.write_document(spec_definition, output_path)

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    dataset_payload = payload["entities"]["simple_analytics"]["datasets"]["my_beautiful_dataset"]
    assert {key: payload[key] for key in ("name", "spec_version", "source")} == {
        "name": "simple_analytics",
        "spec_version": 2,
        "source": {"name": "python_api", "generated": True},
    }
    assert set(payload["functions"]) == {"read", "write", "sum_features", "column_4"}
    assert {
        name: payload["functions"][name]["entrypoint"].rsplit(":", 1)[-1]
        for name in ("read", "write", "sum_features")
    } == {
        "read": "read_data",
        "write": "write_data",
        "sum_features": "sum_features",
    }
    assert set(dataset_payload) == {
        "description",
        "row_scope",
        "order",
        "features",
        "mappings",
    }
    mappings = dataset_payload["mappings"]
    assert mappings["read"]["binding"]["function"] == "read"
    assert mappings["write"]["binding"]["args"]["df"] == "$datasets.@"
    assert mappings["write"]["features"] == {
        "inputs": ["$features.column_3", "$features.column_4"],
        "outputs": [],
    }
    assert mappings["column_3"]["binding"]["args"] == {
        "left_feature": "$features.input_1",
        "right_feature": "$features.input_2",
        "output": "$features.column_3.id",
        "dataset": "$datasets.@.dataframe",
    }
    assert dataset_payload["features"]["column_3"] == {
        "description": "Vectorized feature: column_3",
        "type": None,
        "unit": None,
    }


def test_sources_and_transforms_python_spec() -> None:
    id_dimension = python_spec.dimension.Dimension(id="id", type="integer")
    region_dimension = python_spec.dimension.Dimension(id="region", type="string")
    source = python_spec.entity.Entity(
        id="source",
        name="Source",
        dimensions=[id_dimension],
        datasets=[
            python_spec.dataset.Dataset(
                id="transformed_dataset",
                mappings={
                    "read": python_spec.mapping.FunctionMapping(
                        inputs=[],
                        function=python_spec.ref.function(functions.read_data, operation="read"),
                        arguments={},
                        outputs=[python_spec.feature.Feature(name="input_1")],
                    )
                },
            )
        ],
    )
    target = python_spec.entity.Entity(
        id="transforms_test",
        name="Transforms test",
        dimensions=[id_dimension, region_dimension],
        datasets=[
            python_spec.dataset.Dataset(
                id="target",
                mappings={
                    "read": python_spec.mapping.FunctionMapping(
                        inputs=[],
                        function=python_spec.ref.function(functions.read_data, operation="read"),
                        arguments={},
                        outputs=[python_spec.feature.Feature(name="target_value")],
                    ),
                    "expand_data": python_spec.mapping.FunctionMapping(
                        inputs=[python_spec.ref.feature("input_1")],
                        function=python_spec.ref.function(
                            functions.expand_data, operation="expand"
                        ),
                        arguments={
                            "df1": python_spec.ref.dataset("transformed_dataset").dataframe,
                            "df2": python_spec.ref.current_dataset().dataframe,
                        },
                        outputs=[python_spec.feature.Feature(name="input_2")],
                    ),
                },
            )
        ],
    )
    summary = python_spec.entity.Entity(
        id="summary",
        name="Summary",
        dimensions=[id_dimension],
        datasets=[
            python_spec.dataset.Dataset(
                id="summary",
                mappings={
                    "collapse_data": python_spec.mapping.FunctionMapping(
                        inputs=[python_spec.ref.feature("input_2")],
                        function=python_spec.ref.function(analytics.maximum, operation="collapse"),
                        arguments={
                            "dataset": python_spec.ref.dataset("target").dataframe,
                            "feature": python_spec.ref.feature("input_2").id,
                            "group_by": [python_spec.ref.dimension("id").id],
                            "output": python_spec.ref.feature("collapsed_feature").id,
                        },
                        outputs=[python_spec.feature.Feature(name="collapsed_feature")],
                    )
                },
            )
        ],
    )
    spec_definition = spec.from_python(
        entities=[source, target, summary],
        dimensions=[id_dimension, region_dimension],
        name="transforms_test",
    )

    ds_model = spec_definition.entities["transforms_test"].datasets["target"]
    assert set(ds_model.mappings) == {"read", "expand_data"}
    assert {"target_value", "input_2"} <= set(ds_model.all_features)
    expand = ds_model.mappings["expand_data"]
    assert expand.binding.function == "expand_data"
    assert expand.binding.args == {
        "df1": "$datasets.transformed_dataset.dataframe",
        "df2": "$datasets.@.dataframe",
    }
    assert expand.input_features == ["input_1"]
    collapse = spec_definition.entities["summary"].datasets["summary"].mappings["collapse_data"]
    assert collapse.binding.function == "maximum"
    assert collapse.binding.args == {
        "dataset": "$datasets.target.dataframe",
        "feature": "$features.input_2.id",
        "group_by": ["$dimensions.id.id"],
        "output": "$features.collapsed_feature.id",
    }
    assert collapse.output_features == ["collapsed_feature"]
    assert spec_definition.functions["maximum"].operation == "collapse"
