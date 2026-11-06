import copy
import json
import pathlib
import typing

import pydantic
import pytest

from uptimely import spec
from uptimely.spec import python as python_spec
from uptimely.spec import validation
from uptimely.spec.json import codec
from uptimely.spec.python import conversion


def _document(profiles: object) -> dict[str, typing.Any]:
    return {"profiles": profiles}


def test_keyed_profiles_round_trip_without_repeating_ids(tmp_path: pathlib.Path) -> None:
    document = _document(
        {
            "first": {
                "name": "First Profile",
                "description": "First profile",
                "category": "telemetry",
                "scope": "One row per machine",
            },
            "second": {},
        }
    )
    original = copy.deepcopy(document)
    model = spec.Spec.model_validate(document)
    validation.validate_spec(model)
    payload = codec.to_document(model)

    assert document == original
    assert list(model.profiles) == ["first", "second"]
    assert [profile.id for profile in model.profiles.values()] == ["first", "second"]
    assert all("id" not in profile for profile in payload["profiles"].values())
    assert payload["profiles"]["first"]["name"] == "First Profile"
    assert payload["profiles"]["second"]["name"] == "Second"
    assert model.profiles["second"].name == "Second"
    assert payload["profiles"]["first"]["description"] == "First profile"
    assert payload["profiles"]["first"]["category"] == "telemetry"
    assert payload["profiles"]["first"]["scope"] == "One row per machine"
    assert payload == model.model_dump(exclude_none=False)
    assert payload["spec_version"] == 5
    assert "assembly" in payload["profiles"]["first"]
    assert "mappings" not in payload["profiles"]["first"]

    path = tmp_path / "spec.json"
    spec.write_document(model, path)
    assert json.loads(path.read_text(encoding="utf-8")) == payload
    assert spec.load_spec(path) == model


def test_feature_name_defaults_to_humanized_id() -> None:
    model = spec.Spec.model_validate(
        _document({"telemetry": {"features": {"bearing_temperature": {"type": "float"}}}})
    )

    feature = model.profiles["telemetry"].features["bearing_temperature"]

    assert feature.id == "bearing_temperature"
    assert feature.name == "Bearing Temperature"
    assert (
        codec.to_document(model)["profiles"]["telemetry"]["features"]["bearing_temperature"]["name"]
        == "Bearing Temperature"
    )


def test_operator_id_is_inferred_from_assembly_key() -> None:
    document = _document(
        {
            "telemetry": {
                "assembly": {
                    "calculate": {
                        "compute": {"function": "calculate"},
                    }
                }
            }
        }
    )
    model = spec.Spec.model_validate(document)

    payload = codec.to_document(model)
    operator = payload["profiles"]["telemetry"]["assembly"]["calculate"]

    assert "id" not in operator
    assert set(operator) == {"compute", "interface", "row_context"}
    assert spec.Spec.model_validate(payload) == model


@pytest.mark.parametrize("profiles", [None, "profile", 1, True])
def test_profile_registry_rejects_non_mapping_types(profiles: object) -> None:
    with pytest.raises(pydantic.ValidationError, match="profiles"):
        spec.Spec.model_validate(_document(profiles))


@pytest.mark.parametrize("identifier", ["telemetry", "conflicting"])
def test_profile_attributes_reject_explicit_id(identifier: str) -> None:
    with pytest.raises(pydantic.ValidationError, match="not an 'id' attribute"):
        spec.Spec.model_validate(_document({"telemetry": {"id": identifier}}))


def test_profile_defaults_are_empty_independent_dictionaries() -> None:
    omitted = spec.Spec.model_validate({"profiles": {"values": {}}})
    explicit = spec.Spec.model_validate(_document({"values": {}}))
    assert omitted == explicit
    first = omitted.profiles
    second = explicit.profiles
    first["new"] = spec.Profile(id="new")
    assert second == {"values": second["values"]}


def test_profile_scope_must_be_a_string() -> None:
    with pytest.raises(pydantic.ValidationError, match="scope"):
        spec.Spec.model_validate(_document({"values": {"scope": {"filter": "active"}}}))


def test_python_profile_scope_must_be_a_string() -> None:
    with pytest.raises(TypeError, match="Profile scope must be a string"):
        python_spec.Profile(id="values", scope=1)


@pytest.mark.parametrize("canonical", [False, True])
def test_python_conversion_rejects_duplicate_profile_ids(canonical: bool) -> None:
    declaration = python_spec.profile.Profile(id="duplicate")
    profile = declaration.to_model() if canonical else declaration
    with pytest.raises(ValueError, match="Duplicate profile id duplicate"):
        conversion.to_model(profiles=[profile, profile])
