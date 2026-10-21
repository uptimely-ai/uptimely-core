from collections import abc

import pytest

from uptimely.spec import model as spec_model
from uptimely.spec.python import (
    PythonSpec,
    bind,
    conversion,
    dataset,
    dimension,
    entity,
    feature,
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
    is_expand = category == "expand"
    is_conform = category == "conform"
    return dataset.Dataset(
        id=identifier,
        mappings=[
            mapping.Mapping(
                id=f"{identifier}_mapping",
                bind=bind.bind(
                    ref.function(function, operation=category),
                    function_id=f"{category}_shared",
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
                            "other_dataset": ref.current_dataset().dataframe,
                        }
                        if is_expand or is_conform
                        else {}
                    ),
                    columns=[ref.feature("temperature")],
                ),
                inputs=[ref.feature("temperature")] if is_expand or is_conform else [],
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


def _mapping_source(dimensions: list[dimension.Dimension]) -> entity.Entity:
    return entity.Entity(
        id="source",
        name="Source",
        dimensions=dimensions,
        datasets=[
            dataset.Dataset(
                id="shared_source",
                mappings=[
                    mapping.Mapping(
                        bind=bind.bind(ref.function(_other_source, operation="read")),
                        outputs=[feature.Feature(id="temperature")],
                    )
                ],
            )
        ],
    )


def _conform_source(identifier: str) -> dataset.Dataset:
    return dataset.Dataset(
        id=f"{identifier}_source",
        mappings=[
            mapping.Mapping(
                bind=bind.bind(ref.function(_other_source, operation="read")),
                outputs=[feature.Feature(id="temperature")],
            )
        ],
    )


def test_empty_spec_has_no_datasets_or_functions() -> None:
    spec_definition = PythonSpec()

    assert spec_definition.iter_datasets() == []
    assert spec_definition.function_catalog() == spec_model.FunctionCatalog()
    with pytest.raises(ValueError, match="At least one entity is required"):
        spec_definition.to_dict()


def test_iter_datasets_preserves_entity_and_dataset_order() -> None:
    first = dataset.Dataset(id="first")
    second = dataset.Dataset(id="second")
    third = dataset.Dataset(id="third")
    spec_definition = PythonSpec(
        entities=[_entity("empty", []), _entity("one", [first, second]), _entity("two", [third])]
    )

    assert spec_definition.iter_datasets() == [first, second, third]


def test_function_catalog_keeps_distinct_functions_and_operations() -> None:
    additional = dataset.Dataset(
        id="additional",
        mappings=[mapping.Mapping(bind=bind.bind(ref.function(_other_source, operation="read")))],
    )
    spec_definition = PythonSpec(
        entities=[
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
    spec_definition = PythonSpec(entities=entities)

    catalog = spec_definition.function_catalog()

    function_id = f"{category}_shared"
    assert catalog[function_id] == first.function_catalog()[function_id]
    assert catalog[function_id].entrypoint == f"{__name__}:_source"
    expected_dataframe_inputs = {
        "read": 0,
        "write": 1,
        "vectorize": 1,
        "collapse": 1,
        "expand": 2,
        "conform": 2,
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
            **(
                {
                    "dataset": {"type": "dataframe", "comment": None},
                    "other_dataset": {"type": "dataframe", "comment": None},
                }
                if expected_dataframe_inputs == 2
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
    if expected_dataframe_inputs == 2:
        expected_args["other_dataset"] = "$datasets.@.dataframe"
    assert payload["entities"]["one"]["datasets"][0]["mappings"]["first_mapping"]["binding"] == {
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
    spec_definition = PythonSpec(entities=entities)

    with pytest.raises(
        ValueError, match=f"Conflicting function definition for '{category}_shared'"
    ):
        spec_definition.to_dict()


def test_catalog_conflicts_are_rejected_consistently() -> None:
    first = dataset.Dataset(
        id="first",
        mappings=[
            mapping.Mapping(
                bind=bind.bind(
                    ref.function(_source, operation="read"),
                    function_id="shared",
                    path="readings.json",
                )
            )
        ],
    )
    second = dataset.Dataset(
        id="second",
        mappings=[
            mapping.Mapping(
                bind=bind.bind(
                    ref.function(_source, operation="read"),
                    function_id="shared",
                    path=42,
                )
            )
        ],
    )
    spec_definition = PythonSpec(entities=[_entity("one", [first, second])])

    with pytest.raises(ValueError, match="Conflicting function definition for 'shared'"):
        spec_definition.function_catalog()
    with pytest.raises(ValueError, match="Conflicting function definition for 'shared'"):
        conversion.to_dict(datasets=[first, second])

    combined = dataset.Dataset(id="combined", mappings=[*first.mappings, *second.mappings])
    with pytest.raises(ValueError, match="Conflicting function definition for 'shared'"):
        combined.function_catalog()


@pytest.mark.parametrize("keyed_dimensions", [False, True])
def test_to_dict_preserves_name_dimensions_and_dataset_metadata(
    keyed_dimensions: bool,
) -> None:
    pump = dimension.Dimension(id="pump", type="string", description="Asset ID")
    declaration = dataset.Dataset(
        id="telemetry",
        description="Telemetry readings",
        row_scope=dataset.RowScope(grain="One row per pump", coverage="All pumps"),
        order=[dataset.Order(dimension=ref.dimension("pump"), direction="desc")],
    )
    spec_definition = PythonSpec(
        name="Pump analytics",
        entities=[_entity("assets", [declaration])],
        dimensions={"pump": pump} if keyed_dimensions else [pump],
    )

    payload = spec_definition.to_dict()

    assert payload["name"] == "Pump analytics"
    assert payload["spec_version"] == "0.2.0"
    assert payload["source"] == {"name": "python_api", "generated": True}
    assert payload["dimensions"] == {
        "pump": {"type": "string", "description": "Asset ID", "parent": None}
    }
    assert payload["entities"] == {
        "assets": {
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
