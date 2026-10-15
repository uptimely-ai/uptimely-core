from collections import abc

import pytest

from uptimely.analytics.json import json_model
from uptimely.analytics.python import (
    PythonAnalytics,
    bind,
    dataset,
    dimension,
    entity,
    mapping,
    ref,
)


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
                    ref.function(function),
                    function_id=f"{category}_shared",
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


def test_empty_analytics_has_no_datasets_or_functions() -> None:
    analytics_definition = PythonAnalytics()

    assert analytics_definition.iter_datasets() == []
    assert analytics_definition.function_catalog() == json_model.FunctionCatalog()
    with pytest.raises(ValueError, match="At least one entity is required"):
        analytics_definition.to_analytics_dict()


def test_iter_datasets_preserves_entity_and_dataset_order() -> None:
    first = dataset.Dataset(id="first")
    second = dataset.Dataset(id="second")
    third = dataset.Dataset(id="third")
    analytics_definition = PythonAnalytics(
        entities=[_entity("empty", []), _entity("one", [first, second]), _entity("two", [third])]
    )

    assert analytics_definition.iter_datasets() == [first, second, third]


def test_function_catalog_keeps_distinct_functions_and_operations() -> None:
    additional = dataset.Dataset(
        id="additional",
        mappings=[mapping.Read(bind=bind.bind(ref.function(_other_source)))],
    )
    analytics_definition = PythonAnalytics(
        entities=[
            _entity("one", [_declaration("first", "read")]),
            _entity("two", [additional, _declaration("calculated", "vectorize")]),
        ]
    )

    catalog = analytics_definition.function_catalog()

    assert set(catalog.by_operation("read")) == {"read_shared", "_other_source"}
    assert catalog["_other_source"].entrypoint == f"{__name__}:_other_source"
    assert set(catalog.by_operation("vectorize")) == {"vectorize_shared"}
    assert all(
        not catalog.by_operation(operation)
        for operation in ("write", "collapse", "expand", "conform")
    )


@pytest.mark.parametrize(
    "category", ["read", "write", "vectorize", "collapse", "expand", "conform"]
)
def test_function_catalog_merges_and_deduplicates_each_operation(category: str) -> None:
    first = _declaration("first", category)
    second = _declaration("second", category)
    analytics_definition = PythonAnalytics(
        entities=[_entity("one", [first]), _entity("two", [second])]
    )

    catalog = analytics_definition.function_catalog()

    assert catalog == first.function_catalog()
    function_id = f"{category}_shared"
    assert catalog[function_id].entrypoint == f"{__name__}:_source"
    assert catalog[function_id].args["dataset"].type == "dataframe"
    assert catalog[function_id].args["columns"].type == "array[string]"
    payload = analytics_definition.to_analytics_dict()
    assert payload["functions"][function_id] == {
        "operation": category,
        "entrypoint": f"{__name__}:_source",
        "args": {
            "dataset": {"type": "dataframe", "comment": None},
            "columns": {"type": "array[string]", "comment": None},
        },
    }
    assert payload["entities"]["one"]["datasets"][0]["mappings"]["first_mapping"]["binding"] == {
        "function": function_id,
        "args": {"dataset": "$datasets.@.dataframe", "columns": ["$features.temperature"]},
    }


@pytest.mark.parametrize(
    "category", ["read", "write", "vectorize", "collapse", "expand", "conform"]
)
def test_function_catalog_rejects_conflicting_entrypoints(category: str) -> None:
    analytics_definition = PythonAnalytics(
        entities=[
            _entity("one", [_declaration("first", category)]),
            _entity("two", [_declaration("second", category, _other_source)]),
        ]
    )

    with pytest.raises(
        ValueError, match=f"Conflicting function definition for '{category}_shared'"
    ) as error:
        analytics_definition.to_analytics_dict()

    assert f"{category}/{__name__}:_source vs {category}/{__name__}:_other_source" in str(
        error.value
    )


@pytest.mark.parametrize("keyed_dimensions", [False, True])
def test_to_analytics_dict_preserves_name_dimensions_and_dataset_metadata(
    keyed_dimensions: bool,
) -> None:
    pump = dimension.Dimension(id="pump", type="string", description="Asset ID")
    declaration = dataset.Dataset(
        id="telemetry",
        description="Telemetry readings",
        row_scope=dataset.RowScope(grain="One row per pump", coverage="All pumps"),
        order=[dataset.Order(dimension=ref.dimension("pump"), direction="desc")],
    )
    analytics_definition = PythonAnalytics(
        name="Pump analytics",
        entities=[_entity("assets", [declaration])],
        dimensions={"pump": pump} if keyed_dimensions else [pump],
    )

    payload = analytics_definition.to_analytics_dict()

    assert payload["name"] == "Pump analytics"
    assert payload["version"] == "0.2.0"
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
