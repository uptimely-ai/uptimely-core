import typing

import pytest

from uptimely.spec.json_spec import json_functions, json_model
from uptimely.spec.python_spec import bind, dataset, dimension, entity, mapping, ref


def _source() -> None:
    pass


def _other_source() -> None:
    pass


def _dataset(identifier: str, conflicting: bool = False) -> dataset.Dataset:
    return dataset.Dataset(
        id=identifier,
        mappings=[
            mapping.Read(
                bind=bind.bind(
                    _other_source if conflicting else _source,
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

    payload = json_functions.python_to_spec_dict(
        **({"entities": inputs} if as_entities else {"datasets": inputs}),
        dimensions=[pump],
    )

    assert "name" not in payload
    entity_id = "assets" if as_entities else "entity"
    assert payload["entities"][entity_id]["dimensions"] == ["pump"]
    assert [item["id"] for item in payload["entities"][entity_id]["datasets"]] == [
        "first",
        "second",
    ]
    assert payload["functions"] == {
        "read": {
            "source": {
                "entrypoint": f"{__name__}:_source",
                "args": {
                    "path": {"type": "string", "comment": None},
                    "columns": {"type": "array[string]", "comment": None},
                },
            }
        },
        "write": {},
        "vectorize": {},
        "collapse": {},
        "expand": {},
        "conform": {},
    }


def test_legacy_entities_in_datasets_match_explicit_entities() -> None:
    declarations = [
        entity.Entity(id="assets", name="Assets", dimensions=[], datasets=[_dataset("readings")])
    ]

    assert json_functions.python_to_spec_dict(
        datasets=declarations
    ) == json_functions.python_to_spec_dict(entities=declarations)


@pytest.mark.parametrize("as_entities", [False, True])
def test_auto_catalog_rejects_conflicting_entrypoints(as_entities: bool) -> None:
    declarations = [_dataset("first"), _dataset("second", conflicting=True)]
    inputs = (
        [entity.Entity(id="assets", name="Assets", dimensions=[], datasets=declarations)]
        if as_entities
        else declarations
    )

    with pytest.raises(ValueError, match="Conflicting function id 'source' for read"):
        json_functions.python_to_spec_dict(
            **({"entities": inputs} if as_entities else {"datasets": inputs})
        )


@pytest.mark.parametrize("catalog_form", ["model", "dict", "dict_of_models"])
@pytest.mark.parametrize("canonical_dataset", [False, True])
def test_explicit_catalog_preserves_argument_metadata(
    catalog_form: str, canonical_dataset: bool
) -> None:
    declaration = _dataset("readings")
    catalog = json_model.FunctionCatalog(
        read={
            "source": json_model.ReadFunction(
                id="source",
                entrypoint="custom.reader:load",
                args={
                    "path": json_model.Argument(id="path", type="string", comment="Input path"),
                    "columns": json_model.Argument(id="columns", type="array[string]"),
                },
            )
        }
    )
    functions = {
        "model": catalog,
        "dict": catalog.model_dump(),
        "dict_of_models": {"read": catalog.read},
    }[catalog_form]
    pump = dimension.Dimension(id="pump", type="string")

    payload = json_functions.python_to_spec_dict(
        datasets=[declaration.to_model() if canonical_dataset else declaration],
        functions=functions,
        name="Readings",
        dimensions={"pump": pump.to_model()},
    )

    assert payload["functions"]["read"] == {
        "source": {
            "entrypoint": "custom.reader:load",
            "args": {
                "path": {"type": "string", "comment": "Input path"},
                "columns": {"type": "array[string]", "comment": None},
            },
        }
    }
    assert payload["entities"]["Readings"]["name"] == "Readings"
    assert payload["entities"]["Readings"]["datasets"][0]["id"] == "readings"
    assert payload["dimensions"] == {"pump": pump.to_model().model_dump()}


def test_explicit_catalog_defaults_missing_argument_type_and_skips_unregistered_functions() -> None:
    payload = json_functions.python_to_spec_dict(
        datasets=[_dataset("readings").to_model()],
        functions={"read": {"configured": {"entrypoint": "reader:load", "args": {"value": {}}}}},
    )

    assert payload["functions"]["read"] == {
        "configured": {
            "entrypoint": "reader:load",
            "args": {"value": {"type": "object", "comment": None}},
        }
    }
    assert payload["dimensions"] == {}


@pytest.mark.parametrize(
    ("functions", "expected_function", "expected_entrypoint"),
    [
        (
            json_model.FunctionCatalog(
                read={"source": json_model.ReadFunction(id="source", entrypoint="reader:load")}
            ),
            json_model.ReadFunction(id="source", entrypoint="reader:load"),
            "reader:load",
        ),
        (
            {"read": {"source": json_model.ReadFunction(id="source", entrypoint="reader:load")}},
            json_model.ReadFunction(id="source", entrypoint="reader:load"),
            "reader:load",
        ),
        (
            {"read": {"source": {"entrypoint": "reader:load"}}},
            {"entrypoint": "reader:load"},
            "reader:load",
        ),
        ({"read": {"source": {}}}, {}, "fallback:load"),
        ({"read": {"source": {"entrypoint": ""}}}, {"entrypoint": ""}, "fallback:load"),
        (json_model.FunctionCatalog(), None, "fallback:load"),
        ({}, None, "fallback:load"),
        ({"read": []}, None, "fallback:load"),
        (None, None, "fallback:load"),
    ],
)
def test_configured_function_lookup_and_entrypoint_fallback(
    functions: typing.Any, expected_function: typing.Any, expected_entrypoint: str
) -> None:
    assert json_functions._configured_function(functions, "read", "source") == expected_function
    assert (
        json_functions._configured_entrypoint(functions, "read", "source", "fallback:load")
        == expected_entrypoint
    )


@pytest.mark.parametrize(
    ("kwargs", "error_type", "message"),
    [
        ({"entities": [], "datasets": []}, ValueError, "Use either 'datasets' or 'entities'"),
        ({"entities": []}, ValueError, "At least one entity is required"),
        ({"entities": {}}, ValueError, "At least one entity is required"),
        ({"datasets": []}, ValueError, "At least one dataset is required"),
        ({"datasets": {}}, ValueError, "At least one dataset is required"),
        ({}, ValueError, "At least one dataset is required"),
        ({"datasets": [object()]}, TypeError, "datasets must contain Pydantic models"),
    ],
)
def test_conversion_rejects_invalid_inputs(
    kwargs: dict[str, object], error_type: type[Exception], message: str
) -> None:
    with pytest.raises(error_type, match=message):
        json_functions.python_to_spec_dict(**kwargs)
