import pytest

from uptimely.analytics import model as analytics_model
from uptimely.analytics.python import bind, conversion, dataset, dimension, entity, mapping, ref


def _source() -> None:
    pass


def _other_source() -> None:
    pass


def _dataset(identifier: str, conflicting: bool = False) -> dataset.Dataset:
    return dataset.Dataset(
        id=identifier,
        mappings=[
            mapping.Mapping(
                bind=bind.bind(
                    ref.function(_other_source if conflicting else _source, operation="read"),
                    function_id="source",
                    path="readings.json",
                    columns=[ref.feature("temperature")],
                )
            )
        ],
    )


@pytest.mark.parametrize("keyed", [False, True])
@pytest.mark.parametrize("as_entities", [False, True])
def test_auto_catalog_converts_declaration_lists_and_dicts(keyed: bool, as_entities: bool) -> None:
    declarations = [_dataset("first"), _dataset("second")]
    pump = dimension.Dimension(id="pump", type="string")
    if as_entities:
        resources = [
            entity.Entity(id="assets", name="Assets", dimensions=[pump], datasets=declarations)
        ]
    else:
        resources = declarations
    inputs = {resource.id: resource for resource in resources} if keyed else resources

    payload = conversion.to_dict(
        **({"entities": inputs} if as_entities else {"datasets": inputs}),
        dimensions=[pump],
    )

    assert payload["name"] is None
    entity_id = "assets" if as_entities else "entity"
    assert payload["entities"][entity_id]["dimensions"] == ["pump"]
    assert [item["id"] for item in payload["entities"][entity_id]["datasets"]] == [
        "first",
        "second",
    ]
    assert payload["functions"] == {
        "source": {
            "description": None,
            "operation": "read",
            "returns": "dataframe",
            "entrypoint": f"{__name__}:_source",
            "args": {
                "path": {"type": "string", "comment": None},
                "columns": {"type": "array[string]", "comment": None},
            },
        },
    }


def test_entities_cannot_be_passed_as_datasets() -> None:
    declarations = [
        entity.Entity(id="assets", name="Assets", dimensions=[], datasets=[_dataset("readings")])
    ]

    with pytest.raises(TypeError, match="datasets must contain Dataset"):
        conversion.to_dict(datasets=declarations)


@pytest.mark.parametrize("as_entities", [False, True])
def test_auto_catalog_rejects_conflicting_entrypoints(as_entities: bool) -> None:
    declarations = [_dataset("first"), _dataset("second", conflicting=True)]
    inputs = (
        [entity.Entity(id="assets", name="Assets", dimensions=[], datasets=declarations)]
        if as_entities
        else declarations
    )

    with pytest.raises(ValueError, match="Conflicting function definition for 'source'"):
        conversion.to_dict(**({"entities": inputs} if as_entities else {"datasets": inputs}))


@pytest.mark.parametrize("catalog_form", ["model", "dict", "dict_of_models"])
@pytest.mark.parametrize("canonical_dataset", [False, True])
def test_explicit_catalog_preserves_argument_metadata(
    catalog_form: str, canonical_dataset: bool
) -> None:
    declaration = _dataset("readings")
    catalog = analytics_model.FunctionCatalog(
        root={
            "source": analytics_model.FunctionTemplate(
                id="source",
                operation="read",
                returns="dataframe",
                entrypoint="custom.reader:load",
                args={
                    "path": analytics_model.Argument(
                        id="path", type="string", comment="Input path"
                    ),
                    "columns": analytics_model.Argument(id="columns", type="array[string]"),
                },
            )
        }
    )
    functions = {
        "model": catalog,
        "dict": catalog.model_dump(),
        "dict_of_models": {"source": catalog["source"]},
    }[catalog_form]
    pump = dimension.Dimension(id="pump", type="string")

    payload = conversion.to_dict(
        datasets=[declaration.to_model() if canonical_dataset else declaration],
        functions=functions,
        name="Readings",
        dimensions={"pump": pump.to_model()},
    )

    assert payload["functions"]["source"] == {
        "description": None,
        "operation": "read",
        "returns": "dataframe",
        "entrypoint": "custom.reader:load",
        "args": {
            "path": {"type": "string", "comment": "Input path"},
            "columns": {"type": "array[string]", "comment": None},
        },
    }
    assert payload["entities"]["Readings"]["name"] == "Readings"
    assert payload["entities"]["Readings"]["datasets"][0]["id"] == "readings"
    assert payload["dimensions"] == {"pump": pump.to_model().model_dump()}


def test_explicit_catalog_defaults_missing_argument_type_and_skips_unregistered_functions() -> None:
    payload = conversion.to_dict(
        datasets=[_dataset("readings").to_model()],
        functions={
            "configured": {
                "operation": "read",
                "returns": "dataframe",
                "entrypoint": "reader:load",
                "args": {"value": {"type": "object", "comment": None}},
            }
        },
    )

    assert payload["functions"]["configured"] == {
        "description": None,
        "operation": "read",
        "returns": "dataframe",
        "entrypoint": "reader:load",
        "args": {"value": {"type": "object", "comment": None}},
    }
    assert payload["dimensions"] == {}


@pytest.mark.parametrize(
    ("kwargs", "error_type", "message"),
    [
        ({"entities": [], "datasets": []}, ValueError, "Use either 'datasets' or 'entities'"),
        ({"entities": []}, ValueError, "At least one entity is required"),
        ({"entities": {}}, ValueError, "At least one entity is required"),
        ({"datasets": []}, ValueError, "At least one dataset is required"),
        ({"datasets": {}}, ValueError, "At least one dataset is required"),
        ({}, ValueError, "At least one dataset is required"),
        ({"datasets": [object()]}, TypeError, "datasets must contain Dataset"),
        (
            {"entities": [object()]},
            TypeError,
            "entities must contain Entity",
        ),
        (
            {"datasets": [_dataset("readings")], "dimensions": [object()]},
            TypeError,
            "dimensions must contain Dimension",
        ),
        (
            {"datasets": [_dataset("readings")], "functions": object()},
            TypeError,
            "functions must be a FunctionCatalog",
        ),
    ],
)
def test_conversion_rejects_invalid_inputs(
    kwargs: dict[str, object], error_type: type[Exception], message: str
) -> None:
    with pytest.raises(error_type, match=message):
        conversion.to_dict(**kwargs)
