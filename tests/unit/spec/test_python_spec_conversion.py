from collections import abc

import pytest

from uptimely.spec.json_spec import json_model
from uptimely.spec.python_spec import bind, dataset, dimension, entity, mapping, ref, spec


def _source() -> None:
    pass


def _other_source() -> None:
    pass


def _declaration(
    identifier: str, category: str, function: abc.Callable[..., object] = _source
) -> dataset.Dataset:
    mapping_type = {
        "read": mapping.Read,
        "write": mapping.Write,
        "vectorize": mapping.Vectorize,
        "collapse": mapping.Collapse,
        "expand": mapping.Expand,
        "conform": mapping.Conform,
    }[category]
    return dataset.Dataset(
        id=identifier,
        mappings=[
            mapping_type(
                id=f"{identifier}_mapping",
                bind=bind.bind(
                    function,
                    function_id="shared",
                    dataset=ref.current_dataset().dataframe,
                    columns=[ref.feature("temperature")],
                ),
            )
        ],
    )


def _entity(identifier: str, datasets: list[dataset.Dataset]) -> entity.Entity:
    return entity.Entity(
        id=identifier,
        name=identifier.title(),
        dimensions=[dimension.Dimension(id="pump", type="string")],
        datasets=datasets,
    )


def test_empty_specification_has_no_datasets_or_functions() -> None:
    specification = spec.PythonSpecification()

    assert specification.iter_datasets() == []
    assert specification.function_catalog() == json_model.FunctionCatalog()
    with pytest.raises(ValueError, match="At least one entity is required"):
        specification.to_spec_dict()


def test_iter_datasets_preserves_entity_and_dataset_order() -> None:
    first = dataset.Dataset(id="first")
    second = dataset.Dataset(id="second")
    third = dataset.Dataset(id="third")
    specification = spec.PythonSpecification(
        entities=[_entity("empty", []), _entity("one", [first, second]), _entity("two", [third])]
    )

    assert specification.iter_datasets() == [first, second, third]


def test_function_catalog_keeps_distinct_functions_and_categories() -> None:
    additional = dataset.Dataset(
        id="additional", mappings=[mapping.Read(bind=bind.bind(_other_source))]
    )
    specification = spec.PythonSpecification(
        entities=[
            _entity("one", [_declaration("first", "read")]),
            _entity("two", [additional, _declaration("calculated", "vectorize")]),
        ]
    )

    catalog = specification.function_catalog()

    assert set(catalog.read) == {"shared", "_other_source"}
    assert catalog.read["_other_source"].entrypoint == f"{__name__}:_other_source"
    assert set(catalog.vectorize) == {"shared"}
    assert catalog.write == catalog.collapse == catalog.expand == catalog.conform == {}


@pytest.mark.parametrize(
    "category", ["read", "write", "vectorize", "collapse", "expand", "conform"]
)
def test_function_catalog_merges_and_deduplicates_each_category(category: str) -> None:
    first = _declaration("first", category)
    second = _declaration("second", category)
    specification = spec.PythonSpecification(
        entities=[_entity("one", [first]), _entity("two", [second])]
    )

    catalog = specification.function_catalog()

    assert catalog == first.function_catalog()
    assert getattr(catalog, category)["shared"].entrypoint == f"{__name__}:_source"
    assert getattr(catalog, category)["shared"].args["dataset"].type == "dataframe"
    assert getattr(catalog, category)["shared"].args["columns"].type == "array[string]"
    payload = specification.to_spec_dict()
    assert payload["functions"][category] == {
        "shared": {
            "entrypoint": f"{__name__}:_source",
            "args": {
                "dataset": {"type": "dataframe", "comment": None},
                "columns": {"type": "array[string]", "comment": None},
            },
        }
    }
    assert payload["entities"]["one"]["datasets"][0]["mappings"]["first_mapping"]["binding"] == {
        "function": "shared",
        "args": {"dataset": "$datasets.@.dataframe", "columns": ["$features.temperature"]},
    }


@pytest.mark.parametrize(
    "category", ["read", "write", "vectorize", "collapse", "expand", "conform"]
)
def test_function_catalog_rejects_conflicting_entrypoints(category: str) -> None:
    specification = spec.PythonSpecification(
        entities=[
            _entity("one", [_declaration("first", category)]),
            _entity("two", [_declaration("second", category, _other_source)]),
        ]
    )

    with pytest.raises(
        ValueError, match=f"Conflicting function id 'shared' for {category}"
    ) as error:
        specification.to_spec_dict()

    assert f"{__name__}:_source vs {__name__}:_other_source" in str(error.value)


@pytest.mark.parametrize("keyed_dimensions", [False, True])
def test_to_spec_dict_preserves_name_dimensions_and_dataset_metadata(
    keyed_dimensions: bool,
) -> None:
    pump = dimension.Dimension(id="pump", type="string", description="Asset ID")
    declaration = dataset.Dataset(
        id="telemetry",
        description="Telemetry readings",
        row_scope=dataset.RowScope(grain="One row per pump", coverage="All pumps"),
        order=[dataset.Order(dimension=ref.dimension("pump"), direction="desc")],
    )
    specification = spec.PythonSpecification(
        name="Pump analytics",
        entities=[_entity("assets", [declaration])],
        dimensions={"pump": pump} if keyed_dimensions else [pump],
    )

    payload = specification.to_spec_dict()

    assert payload["name"] == "Pump analytics"
    assert payload["version"] == "0.1.0"
    assert payload["source"] == {"name": "python_api", "generated": True}
    assert payload["dimensions"] == {
        "pump": {"type": "string", "description": "Asset ID", "parent": None}
    }
    assert payload["entities"] == {
        "assets": {
            "id": "assets",
            "name": "Assets",
            "description": None,
            "dimensions": ["pump"],
            "datasets": [
                {
                    "id": "telemetry",
                    "description": "Telemetry readings",
                    "row_scope": {
                        "grain": "One row per pump",
                        "filtering": "",
                        "coverage": "All pumps",
                    },
                    "order": [{"dimension": "$dimensions.pump", "direction": "desc"}],
                    "features": {},
                    "mappings": {},
                }
            ],
        }
    }
