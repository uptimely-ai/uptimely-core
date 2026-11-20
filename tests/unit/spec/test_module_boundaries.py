import copy
import pathlib

import pytest
from support import examples as example_support

import uptimely
from uptimely import spec
from uptimely.codebase.python import entrypoint
from uptimely.compiler import compiler
from uptimely.spec import model, serialization, validation
from uptimely.spec.python import conversion, dimension, profile

SPEC_PATH = example_support.EXAMPLES_ROOT / "artifacts/build/spec.json"


def test_public_models_are_canonical_objects() -> None:
    assert spec.Spec is model.Spec
    assert uptimely.Spec is not model.Spec


@pytest.mark.usefixtures("example_projects")
def test_json_round_trip_preserves_the_document_and_compiled_plan(
    tmp_path: pathlib.Path,
) -> None:
    original_document = serialization.load_document(SPEC_PATH)
    document = spec.load_spec(SPEC_PATH)
    expected = serialization.to_document(document)
    path = tmp_path / "nested" / "spec.json"

    assert serialization.write_document(document, path) == str(path)
    assert serialization.load_document(path) == expected == original_document
    reloaded = spec.load_spec(path)
    assert reloaded == document
    first = compiler.Compiler().compile(document)
    second = compiler.Compiler().compile(reloaded)
    assert {
        item.id: copy.replace(item, dependency_ids=sorted(item.dependency_ids))
        for item in first.invocations
    } == {
        item.id: copy.replace(item, dependency_ids=sorted(item.dependency_ids))
        for item in second.invocations
    }
    assert [set(stage) for stage in first.stages] == [set(stage) for stage in second.stages]


def test_serialization_preserves_function_descriptions_and_profile_ids() -> None:
    document = model.Spec.model_validate(
        {
            "functions": {
                "collapse": {
                    "returns": "dataframe",
                    "entrypoint": "not_installed:collapse",
                    "args": {"dataset": {"type": "dataframe"}},
                },
            },
            "profiles": {"first": {}, "second": {}},
        }
    )

    payload = serialization.to_document(document)

    assert payload["functions"]["collapse"]["description"] is None
    assert list(payload["profiles"]) == ["first", "second"]
    assert all("id" not in profile for profile in payload["profiles"].values())
    assert "id" not in payload["functions"]["collapse"]["args"]["dataset"]
    assert model.Spec.model_validate(payload) == document


@pytest.mark.usefixtures("example_projects")
def test_structural_operations_do_not_inspect_python_entrypoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_inspection(*args: object, **kwargs: object) -> None:
        pytest.fail("Structural operations must not inspect Python entrypoints")

    monkeypatch.setattr(entrypoint, "Entrypoint", unexpected_inspection)
    payload = serialization.load_document(SPEC_PATH)
    document = model.Spec.model_validate(payload)

    assert serialization.to_document(document) == payload
    converted = conversion.to_model(profiles=[profile.Profile(id="assets")])
    assert converted.profiles["assets"].name == "Assets"
    validation.validate_spec(document)
    graph = spec.FeatureGraph(document)
    assert graph.feature_names
    expected_operators = list(document.operators)
    assert all(
        actual is expected
        for actual, expected in zip(graph.operators, expected_operators, strict=True)
    )
    assert spec.load_spec(SPEC_PATH) == document


@pytest.mark.usefixtures("example_projects")
def test_validation_does_not_mutate_the_document() -> None:
    document = model.Spec.model_validate(serialization.load_document(SPEC_PATH))
    before = serialization.to_document(document)

    validation.validate_spec(document)

    assert serialization.to_document(document) == before


def test_python_dictionary_and_json_export_share_the_same_encoding(
    tmp_path: pathlib.Path,
) -> None:
    pump = dimension.Dimension(
        id="pump",
        resolutions=[dimension.Resolution(id="machine", key="pump_id", type="string")],
    )

    class Readings(profile.Profile):
        id = "readings"
        grain = [pump.resolution("machine")]

    declaration = uptimely.Spec(profiles=[Readings])
    document = declaration.to_model()
    path = tmp_path / "spec.json"
    serialization.write_document(document, path)

    assert (
        declaration.to_dict()
        == serialization.to_document(document)
        == serialization.load_document(path)
    )
    assert declaration.to_dict()["name"] is None
    assert "id" not in declaration.to_dict()["profiles"]["readings"]
