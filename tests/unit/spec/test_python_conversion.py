import pytest

from uptimely.spec import model as spec_model
from uptimely.spec.python import assembly, conversion, profile, ref


def _profile(identifier: str, conflicting: bool = False) -> profile.Profile:
    return profile.Profile(
        id=identifier,
        assembly=[
            assembly.Operator(
                id="read",
                interface=assembly.Interface(
                    inputs=[],
                    outputs=[],
                ),
                compute=assembly.Binding(
                    function=ref.FunctionReference(
                        module=__name__ if not conflicting else f"{__name__}.alternate",
                        name="source",
                        returns="dataframe",
                    ),
                    arguments={"path": "readings.json", "columns": [ref.feature("temperature")]},
                ),
            )
        ],
    )


@pytest.mark.parametrize("keyed", [False, True])
def test_auto_catalog_converts_profile_sequences_and_mappings(keyed: bool) -> None:
    declarations = [_profile("first"), _profile("second")]
    inputs = {resource.id: resource for resource in declarations} if keyed else declarations

    payload = conversion.to_dict(profiles=inputs)

    assert payload["name"] is None
    assert list(payload["profiles"]) == ["first", "second"]
    assert all(item["grain"] == [] for item in payload["profiles"].values())
    assert payload["functions"]["source"] == {
        "name": "Source",
        "description": None,
        "category": None,
        "returns": "dataframe",
        "entrypoint": f"{__name__}:source",
        "validate_signature": True,
        "args": {
            "path": {"type": "string", "comment": None},
            "columns": {"type": "array[string]", "comment": None},
        },
    }
    assert set(payload["functions"]) == {"source"}


def test_conversion_rejects_duplicate_and_invalid_profiles() -> None:
    declaration = _profile("readings")
    with pytest.raises(ValueError, match="Duplicate profile id readings"):
        conversion.to_dict(profiles=[declaration, declaration])
    with pytest.raises(TypeError, match="profiles must contain"):
        conversion.to_dict(profiles=[object()])


def test_auto_catalog_rejects_conflicting_entrypoints() -> None:
    declarations = [_profile("first"), _profile("second", conflicting=True)]

    with pytest.raises(ValueError, match="Conflicting function definition for 'source'"):
        conversion.to_dict(profiles=declarations)


@pytest.mark.parametrize("canonical_profile", [False, True])
@pytest.mark.parametrize("catalog_form", ["model", "dict", "dict_of_models"])
def test_explicit_catalog_preserves_argument_metadata(
    catalog_form: str, canonical_profile: bool
) -> None:
    declaration = _profile("readings")
    catalog = spec_model.FunctionCatalog(
        root={
            "source": spec_model.FunctionTemplate(
                id="source",
                returns="dataframe",
                entrypoint="custom.reader:load",
                validate_signature=False,
                args={
                    "path": spec_model.Argument(id="path", type="string", comment="Input path"),
                    "columns": spec_model.Argument(id="columns", type="array[string]"),
                },
            )
        }
    )
    functions = {
        "model": catalog,
        "dict": catalog.model_dump(),
        "dict_of_models": {"source": catalog["source"]},
    }[catalog_form]
    payload = conversion.to_dict(
        profiles=[declaration.to_model() if canonical_profile else declaration],
        functions=functions,
        name="Readings",
    )

    assert payload["functions"]["source"] == {
        "name": "Source",
        "description": None,
        "category": None,
        "returns": "dataframe",
        "entrypoint": "custom.reader:load",
        "validate_signature": False,
        "args": {
            "path": {"type": "string", "comment": "Input path"},
            "columns": {"type": "array[string]", "comment": None},
        },
    }
    assert payload["profiles"]["readings"]["name"] == "Readings"
    assert payload["profiles"]["readings"]["grain"] == []
    assert "id" not in payload["profiles"]["readings"]
    assert payload["dimensions"] == {}


def test_explicit_catalog_defaults_missing_argument_type_and_skips_unregistered_functions() -> None:
    payload = conversion.to_dict(
        profiles=[_profile("readings").to_model()],
        functions={
            "configured": {
                "returns": "dataframe",
                "entrypoint": "reader:load",
                "args": {"value": {"type": "object", "comment": None}},
            }
        },
    )

    assert payload["functions"]["configured"] == {
        "name": "Configured",
        "description": None,
        "category": None,
        "returns": "dataframe",
        "entrypoint": "reader:load",
        "validate_signature": True,
        "args": {"value": {"type": "object", "comment": None}},
    }
    assert payload["dimensions"] == {}


@pytest.mark.parametrize(
    ("kwargs", "error_type", "message"),
    [
        ({"profiles": []}, ValueError, "At least one profile is required"),
        ({"profiles": {}}, ValueError, "At least one profile is required"),
        ({}, ValueError, "At least one profile is required"),
        (
            {"profiles": [_profile("readings")], "dimensions": []},
            TypeError,
            "unexpected keyword argument 'dimensions'",
        ),
        (
            {"profiles": [_profile("readings")], "functions": object()},
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


def test_conversion_rejects_removed_dataframe_argument() -> None:
    with pytest.raises(TypeError, match="unexpected keyword argument 'datasets'"):
        conversion.to_dict(datasets=[_profile("readings")])
