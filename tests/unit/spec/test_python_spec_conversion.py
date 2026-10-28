import dataclasses
from collections import abc

import pytest

from uptimely.spec import model as spec_model
from uptimely.spec.python import (
    Spec,
    actions,
    conversion,
    dataset,
    dimension,
    entity,
    feature,
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
    declarations = [
        actions.Action(
            id=f"{identifier}_mapping",
            inputs=[ref.feature("temperature")] if is_dimensional else [],
            function=ref.function(function, kind=category),
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
    ]
    return dataset.Dataset(
        id=identifier,
        producers=declarations if category not in {"write", "escape"} else [],
        publishers=declarations if category == "write" else [],
        pipelines=declarations if category == "escape" else [],
    )


def _entity(identifier: str, datasets: list[dataset.Dataset]) -> entity.Entity:
    return entity.Entity(
        id=identifier,
        name=identifier.title(),
        dimensions=[dimension.Dimension(id="pump", type="string")],
        datasets=datasets,
    )


def _python_spec(entities: list[entity.Entity], name: str | None = None) -> Spec:
    declarations: list[dataset.Dataset] = []
    for owner in entities:
        for declaration in owner.datasets:
            declaration.entity = owner
            declarations.append(declaration)
    return Spec(
        dimensions=list(
            {item.id: item for owner in entities for item in owner.dimensions}.values()
        ),
        entities=entities,
        datasets=declarations,
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
                producers=[
                    actions.Action(
                        id="_other_source",
                        inputs=[],
                        function=ref.function(_other_source, kind="read"),
                        arguments={},
                        outputs=[feature.Feature(name="temperature")],
                    )
                ],
            )
        ],
    )


def _conform_source(identifier: str) -> dataset.Dataset:
    return dataset.Dataset(
        id=f"{identifier}_source",
        producers=[
            actions.Action(
                id="_other_source",
                inputs=[],
                function=ref.function(_other_source, kind="read"),
                arguments={},
                outputs=[feature.Feature(name="temperature")],
            )
        ],
    )


def test_empty_spec_has_no_datasets_or_functions() -> None:
    spec_definition = Spec(dimensions=[], entities=[], datasets=[])

    assert spec_definition.iter_datasets() == []
    assert spec_definition.function_catalog() == spec_model.FunctionCatalog()
    with pytest.raises(ValueError, match="At least one entity is required"):
        spec_definition.to_dict()


def test_python_spec_requires_a_sequence_and_dataset_entities() -> None:
    with pytest.raises(TypeError, match="datasets must be a sequence"):
        tuple(Spec(dimensions=[], entities=[], datasets={}).datasets)
    with pytest.raises(ValueError, match="Dataset 'readings' must declare an entity"):
        tuple(Spec(dimensions=[], entities=[], datasets=[dataset.Dataset(id="readings")]).datasets)


def test_iter_datasets_preserves_entity_and_dataset_order() -> None:
    first = dataset.Dataset(id="first")
    second = dataset.Dataset(id="second")
    third = dataset.Dataset(id="third")
    spec_definition = _python_spec([_entity("one", [first, second]), _entity("two", [third])])

    assert spec_definition.iter_datasets() == [first, second, third]
    assert [item.id for item in spec_definition.entities] == ["one", "two"]
    assert [item.id for item in spec_definition.entities[0].datasets] == ["first", "second"]
    assert [item.id for item in spec_definition.dimensions] == ["pump"]


def test_python_spec_associates_dataset_classes_with_registered_entity() -> None:
    pump = dimension.Dimension(id="pump", type="string")
    owner = entity.Entity(
        id="assets",
        name="Assets",
        dimensions=[pump],
    )

    class Readings(dataset.Dataset):
        id = "readings"
        entity = owner

    class Summary(dataset.Dataset):
        id = "summary"
        entity = owner

    spec_definition = Spec(dimensions=[pump], entities=[owner], datasets=[Readings, Summary])

    assert [item.id for item in spec_definition.entities] == ["assets"]
    assert [item.id for item in spec_definition.entities[0].datasets] == [
        "readings",
        "summary",
    ]


@pytest.mark.parametrize("entity_id", [False, True])
@pytest.mark.parametrize("dimension_id", [False, True])
def test_python_spec_resolves_registered_ids_and_objects_without_mutation(
    entity_id: bool, dimension_id: bool
) -> None:
    pump = dimension.Dimension(id="pump", type="string", description="Pump identifier")
    owner = entity.Entity(id="assets", name="Assets", dimensions=["pump" if dimension_id else pump])
    readings = _declaration("readings", "read")
    readings.entity = "assets" if entity_id else owner
    definition = Spec(dimensions=[pump], entities=[owner], datasets=[readings])

    document = definition.to_model()
    payload = definition.to_dict()

    assert document.entities["assets"].dimensions[0].id == "pump"
    assert payload["entities"]["assets"]["dimensions"] == ["pump"]
    assert payload["dimensions"]["pump"]["description"] == "Pump identifier"
    canonical = document.entities["assets"].datasets["readings"]
    assert canonical.features["pump"].type == "string"
    assert canonical.actions["readings_mapping"].features.outputs == ["$features.pump"]
    assert readings.entity == ("assets" if entity_id else owner)
    assert owner.dimensions == (["pump"] if dimension_id else [pump])
    assert owner.datasets == []


@pytest.mark.parametrize("omitted", ["dimensions", "entities", "datasets"])
def test_python_spec_requires_all_three_registries(omitted: str) -> None:
    arguments = {"dimensions": [], "entities": [], "datasets": []}
    del arguments[omitted]
    with pytest.raises(TypeError, match=omitted):
        Spec(**arguments)


@pytest.mark.parametrize("object_reference", [False, True])
def test_python_spec_rejects_undeclared_references(object_reference: bool) -> None:
    pump = dimension.Dimension(id="pump", type="string")
    owner = entity.Entity(
        id="assets", name="Assets", dimensions=[pump if object_reference else "pump"]
    )
    readings = dataset.Dataset(id="readings", entity=owner if object_reference else "assets")
    with pytest.raises(ValueError, match="undeclared entity 'assets'"):
        Spec(dimensions=[pump], entities=[], datasets=[readings]).to_model()
    with pytest.raises(ValueError, match="undeclared dimension 'pump'"):
        Spec(dimensions=[], entities=[owner], datasets=[readings]).to_model()


def test_python_spec_rejects_duplicate_registrations_and_conflicting_metadata() -> None:
    pump = dimension.Dimension(id="pump", type="string")
    owner = entity.Entity(id="assets", name="Assets", dimensions=[pump])
    readings = dataset.Dataset(id="readings", entity=owner)
    with pytest.raises(ValueError, match="Duplicate dimension id pump"):
        Spec(dimensions=[pump, pump], entities=[owner], datasets=[readings]).to_model()
    with pytest.raises(ValueError, match="Duplicate entity id assets"):
        Spec(dimensions=[pump], entities=[owner, owner], datasets=[readings]).to_model()
    with pytest.raises(ValueError, match="Duplicate dataset id readings"):
        Spec(dimensions=[pump], entities=[owner], datasets=[readings, readings]).to_model()
    with pytest.raises(ValueError, match="Conflicting metadata for dimension 'pump'"):
        Spec(
            dimensions=[dimension.Dimension(id="pump", type="integer")],
            entities=[owner],
            datasets=[readings],
        ).to_model()
    readings.entity = entity.Entity(id="assets", name="Different", dimensions=[pump])
    with pytest.raises(ValueError, match="Conflicting metadata for entity 'assets'"):
        Spec(dimensions=[pump], entities=[owner], datasets=[readings]).to_model()


def test_python_spec_preserves_unused_registrations_without_inferring_datasets() -> None:
    pump = dimension.Dimension(id="pump", type="string")
    owner = entity.Entity(
        id="assets", name="Assets", dimensions=[], datasets=[dataset.Dataset(id="implicit")]
    )
    definition = Spec(dimensions=[pump], entities=[owner], datasets=[])

    payload = definition.to_dict()

    assert list(payload["dimensions"]) == ["pump"]
    assert payload["entities"]["assets"]["datasets"] == {}
    assert [item.id for item in owner.datasets] == ["implicit"]


def test_python_spec_resolves_mixed_dimension_references_in_declared_order() -> None:
    pump = dimension.Dimension(id="pump", type="string")
    timestamp = dimension.Dimension(id="timestamp", type="datetime")
    owner = entity.Entity(id="assets", name="Assets", dimensions=["timestamp", pump])
    readings = dataset.Dataset(id="readings", entity="assets")
    definition = Spec(dimensions=[pump, timestamp], entities=[owner], datasets=[readings])

    assert definition.to_dict()["entities"]["assets"]["dimensions"] == ["timestamp", "pump"]
    assert [item.id for item in definition.dimensions] == ["pump", "timestamp"]


def test_function_catalog_keeps_distinct_functions_and_kinds() -> None:
    additional = dataset.Dataset(
        id="additional",
        producers=[
            actions.Action(
                id="_other_source",
                inputs=[],
                function=ref.function(_other_source, kind="read"),
                arguments={},
                outputs=[],
            )
        ],
    )
    spec_definition = _python_spec(
        [
            _entity("one", [_declaration("first", "read")]),
            _entity("two", [additional, _declaration("calculated", "vectorize")]),
        ]
    )

    catalog = spec_definition.function_catalog()

    assert set(catalog.by_kind("read")) == {"read_shared", "_other_source"}
    assert catalog["_other_source"].entrypoint == f"{__name__}:_other_source"
    assert set(catalog.by_kind("vectorize")) == {"vectorize_shared"}
    assert all(not catalog.by_kind(kind) for kind in ("write", "collapse", "expand", "conform"))


@pytest.mark.parametrize(
    "category", ["read", "write", "vectorize", "collapse", "expand", "conform"]
)
def test_function_catalog_merges_and_deduplicates_each_kind(category: str) -> None:
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
        "kind": category,
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
    assert payload["entities"]["one"]["datasets"]["first"]["actions"]["first_mapping"][
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
        producers=[
            actions.Action(
                id="_source",
                inputs=[],
                function=ref.function(_source, kind="read"),
                arguments={"path": "readings.json"},
                outputs=[],
                function_id="shared",
            )
        ],
    )
    second = dataset.Dataset(
        id="second",
        producers=[
            actions.Action(
                id="_source",
                inputs=[],
                function=ref.function(_source, kind="read"),
                arguments={"path": 42},
                outputs=[],
                function_id="shared",
            )
        ],
    )
    spec_definition = _python_spec([_entity("one", [first, second])])

    with pytest.raises(ValueError, match="Conflicting function definition for 'shared'"):
        spec_definition.function_catalog()
    with pytest.raises(ValueError, match="Conflicting function definition for 'shared'"):
        conversion.to_dict(datasets=[first, second])

    combined = dataset.Dataset(
        id="combined",
        producers=[
            dataclasses.replace(first.producers[0], id="first"),
            dataclasses.replace(second.producers[0], id="second"),
        ],
    )
    with pytest.raises(ValueError, match="Conflicting function definition for 'shared'"):
        combined.function_catalog()


def test_to_dict_preserves_name_dimensions_and_dataset_metadata() -> None:
    pump = dimension.Dimension(id="pump", type="string", description="Asset ID")
    owner = entity.Entity(
        id="assets",
        name="Assets",
        dimensions=[pump],
    )

    class Telemetry(dataset.Dataset):
        id = "telemetry"
        description = "Telemetry readings"
        entity = owner
        row_scope = dataset.RowScope(grain="One row per pump", coverage="All pumps")
        order = [dataset.Order(dimension=ref.dimension("pump"), direction="desc")]

    spec_definition = Spec(
        dimensions=[pump],
        entities=[owner],
        datasets=[Telemetry],
        name="Pump analytics",
    )

    payload = spec_definition.to_dict()

    assert payload["name"] == "Pump analytics"
    assert payload["spec_version"] == 3
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
                    "actions": {},
                }
            },
        }
    }
