import json
import pathlib

from examples.pump_analytics.config.analytics import analytics as pump_telemetry_analytics
from examples.pump_analytics.config.analytics import dimension as pump_dimensions
from examples.pump_analytics.config.analytics import entity as pump_entities
from examples.pump_analytics.functions import calculation
from examples.simple_analytics.config.analytics import analytics as simple_analytics_module
from examples.simple_analytics.functions import functions

from uptimely import analytics
from uptimely.analytics import python as python_analytics
from uptimely.analytics.python import bind

ANALYTICS_PATH = pathlib.Path("examples/pump_analytics/_generated/spec/spec.json")


def test_pump_dimensions_are_collected_in_declaration_order() -> None:
    expected = [
        pump_dimensions.PLANT,
        pump_dimensions.PRODUCTION_LINE,
        pump_dimensions.PUMP,
        pump_dimensions.TIMESTAMP,
    ]

    assert pump_dimensions.dimensions == expected
    assert list(pump_dimensions.by_id) == ["plant", "production_line", "pump", "timestamp"]
    for declaration in expected:
        assert pump_dimensions.by_id[declaration.id] is declaration
    assert pump_telemetry_analytics.dimensions is pump_dimensions.dimensions
    assert pump_dimensions.PRODUCTION_LINE.parent == pump_dimensions.PLANT.id
    assert pump_dimensions.PUMP.parent == pump_dimensions.PRODUCTION_LINE.id


def test_pump_entities_are_collected_in_declaration_order() -> None:
    expected = [pump_entities.PUMP_TELEMETRY, pump_entities.PUMP]

    assert pump_entities.entities == expected
    assert list(pump_entities.by_id) == ["pump_telemetry", "pump"]
    for declaration in expected:
        assert pump_entities.by_id[declaration.id] is declaration
    assert pump_telemetry_analytics.entities is pump_entities.entities
    assert pump_entities.PUMP_TELEMETRY.dimensions == pump_dimensions.dimensions
    assert pump_entities.PUMP.dimensions == [
        pump_dimensions.PLANT,
        pump_dimensions.PRODUCTION_LINE,
        pump_dimensions.PUMP,
    ]


def test_argument_definition_supports_recursive_compact_types() -> None:
    assert bind._argument_definition({"value": 1.0}) == {"type": "object{str: float}"}
    assert bind._argument_definition({"value": {"nested": 1.0}}) == {
        "type": "object{str: object{str: float}}"
    }
    assert bind._argument_definition({"dimensions": [python_analytics.ref.dimension("plant")]}) == {
        "type": "object{str: array[string]}"
    }
    assert bind._argument_definition({"value": 1.0, "other": "text"}) == {"type": "object"}


def test_function_catalog_uses_vectorize_category() -> None:
    analytics_definition = analytics.Analytics(json=ANALYTICS_PATH)

    categories = set(analytics_definition.functions.model_dump(exclude_none=True))
    assert "vectorize" in categories


def test_example_manifest_parses_complete_analytics() -> None:
    analytics_definition = analytics.Analytics(json=ANALYTICS_PATH)
    analytics_from_directory = analytics.Analytics(json=ANALYTICS_PATH.parent)

    assert analytics_from_directory.path.endswith("spec.json")
    assert analytics_definition.dimensions["pump"].parent == "production_line"
    assert set(analytics_definition.entities) == {"pump_telemetry", "pump"}
    assert analytics_definition.entities["pump_telemetry"].dimension_ids == [
        "plant",
        "production_line",
        "pump",
        "timestamp",
    ]
    assert analytics_definition.entities["pump_telemetry"].dimensions == [
        analytics_definition.dimensions[identifier]
        for identifier in ("plant", "production_line", "pump", "timestamp")
    ]
    assert isinstance(analytics_definition, analytics.Analytics)
    assert analytics_definition.source.name == "python_api"
    assert analytics_definition.source.generated is True
    assert set(analytics_definition.functions.model_dump(exclude_none=True)) == {
        "read",
        "write",
        "vectorize",
        "collapse",
        "expand",
        "conform",
    }
    assert set(analytics_definition.functions.vectorize) - {"maximum"} == {
        function.id for function in analytics_definition.resolved_functions
    }
    assert len(analytics_definition.resolved_functions) == 7

    pump_dataset = analytics_definition.entities["pump"].datasets[0]
    collapse = pump_dataset.mappings["bearing_temperature_by_pump"]
    assert not hasattr(collapse, "source")
    assert collapse.binding.function == "maximum"
    assert "bearing_temperature_max" in collapse.output_features


def test_analytics_from_entities_python_api(tmp_path: pathlib.Path) -> None:
    analytics_definition = analytics.Analytics.from_python(
        entities=simple_analytics_module.python_analytics.entities,
        dimensions=simple_analytics_module.python_analytics.dimensions,
        name=simple_analytics_module.python_analytics.name,
    )

    assert (
        analytics_definition.entities["simple_analytics"].datasets[0].id == "my_beautiful_dataset"
    )
    assert analytics_definition.name == "Simple analytics"
    assert analytics_definition.source.name == "python_api"
    assert analytics_definition.source.generated is True
    assert analytics_definition.functions.read


def test_example_timestamp_order_matches_python_declaration() -> None:
    authored = analytics.Analytics.from_python(
        entities=pump_telemetry_analytics.entities, dimensions=pump_telemetry_analytics.dimensions
    )
    exported = analytics.Analytics(json=ANALYTICS_PATH)
    expected = [{"dimension": "$dimensions.timestamp", "direction": "asc"}]
    for analytics_definition in (authored, exported):
        assert [
            key.model_dump()
            for key in analytics_definition.entities["pump_telemetry"].datasets[0].order
        ] == expected
        assert analytics_definition.entities["pump"].datasets[0].order == []


def test_analytics_from_python_models_and_json_export(tmp_path: pathlib.Path) -> None:
    analytics_definition = analytics.Analytics.from_python(
        datasets=[simple_analytics_module.dataset_],
        functions=simple_analytics_module.dataset_.function_catalog(),
        name="simple_analytics",
        dimensions=simple_analytics_module.dimensions,
    )
    output_path = tmp_path / "spec.json"
    analytics_definition.to_json(output_path)

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    dataset_payload = payload["entities"]["simple_analytics"]["datasets"][0]
    assert {key: payload[key] for key in ("name", "version", "source")} == {
        "name": "simple_analytics",
        "version": "0.1.0",
        "source": {"name": "python_api", "generated": True},
    }
    assert set(payload["functions"]) == {"read", "write", "vectorize"}
    assert {
        name: payload["functions"][category][name]["entrypoint"].rsplit(":", 1)[-1]
        for category, name in (
            ("read", "read"),
            ("write", "write"),
            ("vectorize", "sum_features"),
        )
    } == {
        "read": "read_data",
        "write": "write_data",
        "sum_features": "sum_features",
    }
    assert set(dataset_payload) == {
        "id",
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
        "output": "$features.column_3",
        "dataset": "$datasets.@.dataframe",
    }
    assert dataset_payload["features"]["column_3"] == {
        "description": "Vectorized feature: column_3",
        "type": None,
        "unit": None,
    }


def test_sources_and_transforms_python_analytics() -> None:
    declaration = python_analytics.dataset.Dataset(
        id="transformed_dataset",
        mappings=[
            python_analytics.mapping.Read(
                id="read",
                bind=bind.bind(python_analytics.ref.function(functions.read_data)),
                outputs=[python_analytics.feature.Feature(id="input_1")],
            ),
            python_analytics.mapping.Expand(
                id="expand_data",
                bind=bind.bind(
                    python_analytics.ref.function(functions.expand_data),
                    df1=python_analytics.ref.dataset("transformed_dataset"),
                    df2=python_analytics.ref.dataset("transformed_dataset"),
                ),
                outputs=[python_analytics.feature.Feature(id="input_2")],
            ),
        ],
    )
    summary = python_analytics.dataset.Dataset(
        id="summary",
        mappings=[
            python_analytics.mapping.Collapse(
                id="collapse_data",
                bind=bind.bind(
                    python_analytics.ref.function(calculation.maximum),
                    feature=python_analytics.ref.feature("input_1"),
                ),
                inputs=[python_analytics.ref.feature("input_1")],
                outputs=[python_analytics.feature.Feature(id="collapsed_feature")],
            )
        ],
    )
    analytics_definition = analytics.Analytics.from_python(
        datasets=[declaration, summary],
        name="transforms_test",
    )

    ds_model = analytics_definition.entities["transforms_test"].datasets[0]
    assert set(ds_model.mappings) == {"read", "expand_data"}
    assert {"input_1", "input_2"} <= set(ds_model.all_features)
    collapse = (
        analytics_definition.entities["transforms_test"].datasets[1].mappings["collapse_data"]
    )
    assert collapse.binding.function == "maximum"
    assert collapse.binding.args == {"feature": "$features.input_1"}
    assert collapse.output_features == ["collapsed_feature"]
    assert "maximum" in analytics_definition.functions.collapse
