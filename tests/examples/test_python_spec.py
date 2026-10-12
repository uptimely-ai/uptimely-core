import json
from pathlib import Path

from uptimely.spec import Specification
from uptimely.spec.python_spec import bind, dataset, feature, mapping, ref
from uptimely.spec.python_spec.bind import _argument_definition

SPEC_PATH = Path("examples/example_1/_generated/spec/spec.json")


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

    assert specification_from_directory.path.endswith("spec.json")
    assert specification.dimensions["pump"].parent == "production_line"
    assert set(specification.entities) == {"pump_telemetry", "pump"}
    assert specification.entities["pump_telemetry"].dimensions == [
        "plant",
        "production_line",
        "pump",
        "timestamp",
    ]
    assert isinstance(specification, Specification)
    assert specification.source.name == "python_api"
    assert specification.source.generated is True
    assert set(specification.functions.model_dump(exclude_none=True)) == {
        "read",
        "write",
        "vectorize",
        "collapse",
        "expand",
        "conform",
    }
    assert set(specification.functions.vectorize) - {"maximum"} == {
        function.id for function in specification.resolved_functions
    }
    assert len(specification.resolved_functions) == 8

    pump_dataset = specification.entities["pump"].datasets[0]
    collapse = pump_dataset.mappings["bearing_temperature_by_pump"]
    assert not hasattr(collapse, "source")
    assert collapse.binding.function == "maximum"
    assert "bearing_temperature_max" in collapse.features


def test_spec_from_entities_python_api(tmp_path: Path) -> None:
    from examples.example_2.spec.spec import python_specification

    specification = Specification.from_python(
        entities=python_specification.entities,
        dimensions=python_specification.dimensions,
        name=python_specification.name,
    )

    assert specification.entities["example_2"].datasets[0].id == "my_beautiful_dataset"
    assert specification.name == "Example 2"
    assert specification.source.name == "python_api"
    assert specification.source.generated is True
    assert specification.functions.read


def test_example_timestamp_order_matches_python_declaration() -> None:
    from examples.example_1.spec.spec import dimensions, entities

    authored = Specification.from_python(entities=entities, dimensions=dimensions)
    exported = Specification.from_json(SPEC_PATH)
    expected = [{"dimension": "$dimensions.timestamp", "direction": "asc"}]
    for specification in (authored, exported):
        assert [
            key.model_dump() for key in specification.entities["pump_telemetry"].datasets[0].order
        ] == expected
        assert specification.entities["pump"].datasets[0].order == []


def test_spec_from_python_models_and_json_export(tmp_path: Path) -> None:
    from examples.example_2.spec.spec import dataset_, dimensions

    specification = Specification.from_python(
        datasets=[dataset_],
        functions=dataset_.function_catalog(),
        name="example_2",
        dimensions=dimensions,
    )
    output_path = tmp_path / "spec.json"
    specification.to_json(output_path)

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    dataset_payload = payload["entities"]["example_2"]["datasets"][0]
    assert {key: payload[key] for key in ("name", "version", "source")} == {
        "name": "example_2",
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
    assert mappings["write"]["features"] == []
    assert mappings["column_3"]["binding"]["args"] == {
        "left_feature": "$features.input_1",
        "right_feature": "$features.input_2",
        "output": "$features.column_3",
    }
    assert dataset_payload["features"]["column_3"] == {
        "description": "Vectorized feature: column_3",
        "type": None,
        "unit": None,
        "row_context": None,
    }


def test_sources_and_transforms_python_spec() -> None:
    from examples.example_1.functions.calculation import maximum
    from examples.example_2.functions import functions

    declaration = dataset.Dataset(
        id="transformed_dataset",
        mappings=[
            mapping.Read(
                id="read",
                bind=bind.bind(functions.read_data),
                features=[feature.Feature(id="input_1")],
            ),
            mapping.Expand(
                id="expand_data",
                bind=bind.bind(
                    functions.expand_data,
                    df1=ref.dataset("transformed_dataset"),
                    df2=ref.dataset("transformed_dataset"),
                ),
                features=[feature.Feature(id="input_2")],
            ),
        ],
    )
    summary = dataset.Dataset(
        id="summary",
        mappings=[
            mapping.Collapse(
                id="collapse_data",
                bind=bind.bind(maximum, feature=ref.feature("input_1")),
                features=[feature.Feature(id="collapsed_feature")],
            )
        ],
    )
    spec = Specification.from_python(
        datasets=[declaration, summary],
        name="transforms_test",
    )

    ds_model = spec.entities["transforms_test"].datasets[0]
    assert set(ds_model.mappings) == {"read", "expand_data"}
    assert {"input_1", "input_2"} <= set(ds_model.all_features)
    collapse = spec.entities["transforms_test"].datasets[1].mappings["collapse_data"]
    assert collapse.binding.function == "maximum"
    assert collapse.binding.args == {"feature": "$features.input_1"}
    assert collapse.features == ["collapsed_feature"]
    assert "maximum" in spec.functions.collapse
