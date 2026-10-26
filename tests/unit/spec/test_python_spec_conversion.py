from collections import abc

import pytest

from uptimely.spec import model as spec_model
from uptimely.spec.python import (
    PythonSpec,
    conversion,
    dataset,
    dimension,
    entity,
    feature,
    mapping,
    ref,
)


def _source(
    columns: list[str] | None = None,
    path: str | int | None = None,
    dataset: object = None,
    other_dataset: object = None,
) -> None:
    pass


def _other_source(
    columns: list[str] | None = None,
    path: str | int | None = None,
    dataset: object = None,
    other_dataset: object = None,
) -> None:
    pass


def _declaration(
    identifier: str, category: str, function: abc.Callable[..., object] = _source
) -> dataset.Dataset:
    is_expand = category == "expand"
    is_dimensional = category in {"conform", "expand"}
    return dataset.Dataset(
        id=identifier,
        mappings={
            f"{identifier}_mapping": mapping.FunctionMapping(
                inputs=[ref.feature("temperature")] if is_dimensional else [],
                function=ref.function(function, operation=category),
                arguments={
                    **(
                        {"dataset": ref.current_dataset().dataframe}
                        if category in {"write", "vectorize", "collapse"}
                        else {}
                    ),
                    **(
                        {
                            "dataset": ref.dataset(
                                "shared_source" if is_expand else f"{identifier}_source"
                            ).dataframe,
                        }
                        if is_dimensional
                        else {}
                    ),
                    "columns": [ref.feature("temperature")],
                },
                outputs=[],
                function_id=f"{category}_shared",
            )
        },
    )


def _entity(identifier: str, datasets: list[dataset.Dataset]) -> entity.Entity:
    return entity.Entity(
        id=identifier,
        name=identifier.title(),
        dimensions=[dimension.Dimension(id="pump", type="string")],
        datasets=datasets,
    )


def _python_spec(entities: list[entity.Entity], name: str | None = None) -> PythonSpec:
    return PythonSpec(
        datasets={declaration: declaration.datasets for declaration in entities},
        name=name,
    )


def _mapping_source(dimensions: list[dimension.Dimension]) -> entity.Entity:
    return entity.Entity(
        id="source",
        name="Source",
        dimensions=dimensions,
        datasets=[
            dataset.Dataset(
                id="shared_source",
                mappings={
                    "_other_source": mapping.FunctionMapping(
                        inputs=[],
                        function=ref.function(_other_source, operation="read"),
                        arguments={},
                        outputs=[feature.Feature(name="temperature")],
                    )
                },
            )
        ],
    )


def _conform_source(identifier: str) -> dataset.Dataset:
    return dataset.Dataset(
        id=f"{identifier}_source",
        mappings={
            "_other_source": mapping.FunctionMapping(
                inputs=[],
                function=ref.function(_other_source, operation="read"),
                arguments={},
                outputs=[feature.Feature(name="temperature")],
            )
        },
    )


def test_empty_spec_has_no_datasets_or_functions() -> None:
    spec_definition = PythonSpec(datasets={})

    assert spec_definition.iter_datasets() == []
    assert spec_definition.function_catalog() == spec_model.FunctionCatalog()
    with pytest.raises(ValueError, match="At least one entity is required"):
        spec_definition.to_dict()


def test_iter_datasets_preserves_entity_and_dataset_order() -> None:
    first = dataset.Dataset(id="first")
    second = dataset.Dataset(id="second")
    third = dataset.Dataset(id="third")
    spec_definition = _python_spec(
        [_entity("empty", []), _entity("one", [first, second]), _entity("two", [third])]
    )

    assert spec_definition.iter_datasets() == [first, second, third]
    assert [item.id for item in spec_definition.entities] == ["empty", "one", "two"]
    assert [item.id for item in spec_definition.entities[1].datasets] == ["first", "second"]
    assert [item.id for item in spec_definition.dimensions] == ["pump"]


def test_function_catalog_keeps_distinct_functions_and_operations() -> None:
    additional = dataset.Dataset(
        id="additional",
        mappings={
            "_other_source": mapping.FunctionMapping(
                inputs=[],
                function=ref.function(_other_source, operation="read"),
                arguments={},
                outputs=[],
            )
        },
    )
    spec_definition = _python_spec(
        [
            _entity("one", [_declaration("first", "read")]),
            _entity("two", [additional, _declaration("calculated", "vectorize")]),
        ]
    )

    catalog = spec_definition.function_catalog()

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
    first_datasets = [first]
    second_datasets = [second]
    if category == "conform":
        first_datasets.append(_conform_source("first"))
        second_datasets.append(_conform_source("second"))
    entities = [_entity("one", first_datasets), _entity("two", second_datasets)]
    if category == "expand":
        entities.insert(0, _mapping_source([]))
    spec_definition = _python_spec(entities)

    catalog = spec_definition.function_catalog()

    function_id = f"{category}_shared"
    assert catalog[function_id] == first.function_catalog()[function_id]
    assert catalog[function_id].entrypoint == f"{__name__}:_source"
    expected_dataframe_inputs = {
        "read": 0,
        "write": 1,
        "vectorize": 1,
        "collapse": 1,
        "expand": 1,
        "conform": 1,
    }[category]
    assert sum(arg.type == "dataframe" for arg in catalog[function_id].args.values()) == (
        expected_dataframe_inputs
    )
    assert catalog[function_id].args["columns"].type == "array[string]"
    payload = spec_definition.to_dict()
    assert payload["functions"][function_id] == {
        "description": None,
        "operation": category,
        "returns": "none" if category == "write" else "dataframe",
        "entrypoint": f"{__name__}:_source",
        "validate_signature": True,
        "args": {
            "columns": {"type": "array[string]", "comment": None},
            **(
                {"dataset": {"type": "dataframe", "comment": None}}
                if expected_dataframe_inputs == 1
                else {}
            ),
        },
    }
    expected_args = {"columns": ["$features.temperature"]}
    if expected_dataframe_inputs:
        source_id = (
            "shared_source"
            if category == "expand"
            else "first_source"
            if category == "conform"
            else "@"
        )
        expected_args["dataset"] = f"$datasets.{source_id}.dataframe"
    assert payload["entities"]["one"]["datasets"]["first"]["mappings"]["first_mapping"][
        "binding"
    ] == {
        "function": function_id,
        "args": expected_args,
    }


@pytest.mark.parametrize(
    "category", ["read", "write", "vectorize", "collapse", "expand", "conform"]
)
def test_function_catalog_rejects_conflicting_entrypoints(category: str) -> None:
    first_datasets = [_declaration("first", category)]
    second_datasets = [_declaration("second", category, _other_source)]
    if category == "conform":
        first_datasets.append(_conform_source("first"))
        second_datasets.append(_conform_source("second"))
    entities = [_entity("one", first_datasets), _entity("two", second_datasets)]
    if category == "expand":
        entities.insert(0, _mapping_source([]))
    spec_definition = _python_spec(entities)

    with pytest.raises(
        ValueError, match=f"Conflicting function definition for '{category}_shared'"
    ):
        spec_definition.to_dict()


def test_catalog_conflicts_are_rejected_consistently() -> None:
    first = dataset.Dataset(
        id="first",
        mappings={
            "_source": mapping.FunctionMapping(
                inputs=[],
                function=ref.function(_source, operation="read"),
                arguments={"path": "readings.json"},
                outputs=[],
                function_id="shared",
            )
        },
    )
    second = dataset.Dataset(
        id="second",
        mappings={
            "_source": mapping.FunctionMapping(
                inputs=[],
                function=ref.function(_source, operation="read"),
                arguments={"path": 42},
                outputs=[],
                function_id="shared",
            )
        },
    )
    spec_definition = _python_spec([_entity("one", [first, second])])

    with pytest.raises(ValueError, match="Conflicting function definition for 'shared'"):
        spec_definition.function_catalog()
    with pytest.raises(ValueError, match="Conflicting function definition for 'shared'"):
        conversion.to_dict(datasets=[first, second])

    combined = dataset.Dataset(
        id="combined",
        mappings={
            "first": next(iter(first.mappings.values())),
            "second": next(iter(second.mappings.values())),
        },
    )
    with pytest.raises(ValueError, match="Conflicting function definition for 'shared'"):
        combined.function_catalog()


def test_to_dict_preserves_name_dimensions_and_dataset_metadata() -> None:
    pump = dimension.Dimension(id="pump", type="string", description="Asset ID")
    declaration = dataset.Dataset(
        id="telemetry",
        description="Telemetry readings",
        row_scope=dataset.RowScope(grain="One row per pump", coverage="All pumps"),
        order=[dataset.Order(dimension=ref.dimension("pump"), direction="desc")],
    )
    spec_definition = PythonSpec(
        datasets={
            entity.Entity(
                id="assets",
                name="Assets",
                dimensions=[pump],
            ): [declaration]
        },
        name="Pump analytics",
    )

    payload = spec_definition.to_dict()

    assert payload["name"] == "Pump analytics"
    assert payload["spec_version"] == 2
    assert payload["source"] == {"name": "python_api", "generated": True}
    assert payload["dimensions"] == {
        "pump": {"type": "string", "description": "Asset ID", "parent": None}
    }
    assert payload["entities"] == {
        "assets": {
            "name": "Assets",
            "description": None,
            "dimensions": ["pump"],
            "datasets": {
                "telemetry": {
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
            },
        }
    }
