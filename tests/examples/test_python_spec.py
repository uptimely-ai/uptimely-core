import polars as pl
from conftest import EXAMPLES_ROOT
from examples.pump_analytics.functions import analytics
from examples.pump_analytics.spec import dimension as pump_dimensions
from examples.pump_analytics.spec import entity as pump_entities
from examples.pump_analytics.spec import spec as pump_telemetry_spec

from uptimely import spec
from uptimely.spec import python as python_spec
from uptimely.spec.python import binding_conversion

SPEC_PATH = EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json"


def _read_transform_data() -> pl.DataFrame:
    return pl.DataFrame({"id": [1, 2], "input_1": [1, 3], "input_2": [2, 4]})


def expand_data(source: pl.DataFrame) -> pl.DataFrame:
    return source.select("id", pl.col("input_1").alias("expanded"))


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
    assert [declaration.id for declaration in pump_telemetry_spec.python_spec.datasets] == [
        "pump_telemetry_dataset",
        "pump_dataset",
        "pump_external_workflow_dataset",
    ]
    assert [
        dataset.id
        for entity in pump_telemetry_spec.python_spec.entities
        for dataset in entity.datasets
    ] == ["pump_telemetry_dataset", "pump_dataset", "pump_external_workflow_dataset"]


def test_argument_definition_supports_recursive_compact_types() -> None:
    assert binding_conversion.argument_definition({"value": 1.0}) == {"type": "object{str: float}"}
    assert binding_conversion.argument_definition({"value": {"nested": 1.0}}) == {
        "type": "object{str: object{str: float}}"
    }
    assert binding_conversion.argument_definition(
        {"dimensions": [python_spec.ref.dimension("plant")]}
    ) == {"type": "object{str: array[string]}"}
    assert binding_conversion.argument_definition({"value": 1.0, "other": "text"}) == {
        "type": "object"
    }


def test_function_catalog_functions_declare_kinds() -> None:
    spec_definition = spec.load_spec(SPEC_PATH)

    function_kinds = {function.kind for function in spec_definition.functions.root.values()}
    assert "vectorize" in function_kinds


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
    assert {function.kind for function in spec_definition.functions.root.values()} == {
        "read",
        "write",
        "vectorize",
        "collapse",
        "escape",
    }
    assert "maximum" not in spec_definition.functions.by_kind("vectorize")
    assert len(spec_definition.functions.by_kind("vectorize")) == 7

    pump_dataset = spec_definition.entities["pump"].datasets["pump_dataset"]
    collapse = pump_dataset.mappings["bearing_temperature_by_pump"]
    assert not hasattr(collapse, "source")
    assert collapse.binding.function == "maximum"
    assert "bearing_temperature_max" in collapse.output_features


def test_spec_from_entities_python_api() -> None:
    spec_definition = spec.from_python(
        entities=pump_telemetry_spec.python_spec.entities,
        dimensions=pump_telemetry_spec.python_spec.dimensions,
        name=pump_telemetry_spec.python_spec.name,
    )

    assert set(spec_definition.entities) == {"pump_telemetry", "pump"}
    assert spec_definition.name == pump_telemetry_spec.python_spec.name
    assert spec_definition.source.name == "python_api"
    assert spec_definition.source.generated is True
    assert spec_definition.functions.by_kind("read")


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
                        function=python_spec.ref.function(_read_transform_data, kind="read"),
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
                        function=python_spec.ref.function(_read_transform_data, kind="read"),
                        arguments={},
                        outputs=[python_spec.feature.Feature(name="target_value")],
                    ),
                    "expand_data": python_spec.mapping.FunctionMapping(
                        inputs=[python_spec.ref.feature("input_1")],
                        function=python_spec.ref.function(expand_data, kind="expand"),
                        arguments={
                            "source": python_spec.ref.dataset("transformed_dataset").dataframe,
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
                        function=python_spec.ref.function(analytics.maximum, kind="collapse"),
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
        "source": "$datasets.transformed_dataset.dataframe",
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
    assert spec_definition.functions["maximum"].kind == "collapse"
