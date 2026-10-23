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


def _document(datasets: object) -> dict[str, typing.Any]:
    return {"entities": {"asset": {"name": "Asset", "datasets": datasets}}}


def test_keyed_datasets_round_trip_without_repeating_ids(tmp_path: pathlib.Path) -> None:
    document = _document(
        {
            "first": {
                "description": "First dataset",
                "row_scope": {"grain": "One row per asset"},
            },
            "second": {},
        }
    )
    original = copy.deepcopy(document)
    model = spec.Spec.model_validate(document)
    validation.validate_spec(model)
    payload = codec.to_document(model)

    assert document == original
    assert list(model.entities["asset"].datasets) == ["first", "second"]
    assert [dataset.id for dataset in model.entities["asset"].datasets.values()] == [
        "first",
        "second",
    ]
    datasets = payload["entities"]["asset"]["datasets"]
    assert all("id" not in dataset for dataset in datasets.values())
    assert datasets["first"]["description"] == "First dataset"
    assert datasets["first"]["row_scope"]["grain"] == "One row per asset"
    assert payload == model.model_dump(exclude_none=False)
    assert payload["spec_version"] == 2

    path = tmp_path / "spec.json"
    spec.write_document(model, path)
    assert json.loads(path.read_text(encoding="utf-8")) == payload
    assert spec.load_spec(path) == model


@pytest.mark.parametrize("datasets", [[], [{"id": "old"}], None, "dataset", 1, True])
def test_dataset_registry_rejects_old_arrays_and_invalid_types(datasets: object) -> None:
    with pytest.raises(pydantic.ValidationError, match="datasets"):
        spec.Spec.model_validate(_document(datasets))


@pytest.mark.parametrize("identifier", ["telemetry", "conflicting"])
def test_dataset_attributes_reject_explicit_id(identifier: str) -> None:
    with pytest.raises(pydantic.ValidationError, match="not an 'id' attribute"):
        spec.Spec.model_validate(_document({"telemetry": {"id": identifier}}))


def test_dataset_defaults_are_empty_independent_dictionaries() -> None:
    omitted = spec.Spec.model_validate({"entities": {"asset": {"name": "Asset"}}})
    explicit = spec.Spec.model_validate(_document({}))
    assert omitted == explicit
    first = omitted.entities["asset"].datasets
    second = explicit.entities["asset"].datasets
    first["new"] = spec.Dataset(id="new")
    assert second == {}


@pytest.mark.parametrize("explicit_entity", [False, True])
@pytest.mark.parametrize("canonical", [False, True])
def test_python_conversion_rejects_duplicate_dataset_ids(
    explicit_entity: bool, canonical: bool
) -> None:
    declaration = python_spec.dataset.Dataset(id="duplicate")
    with pytest.raises(ValueError, match="Duplicate dataset id duplicate"):
        if explicit_entity:
            conversion.to_model(
                entities=[
                    python_spec.entity.Entity(
                        id="asset",
                        name="Asset",
                        dimensions=[],
                        datasets=[declaration, declaration],
                    )
                ]
            )
        else:
            dataset = declaration.to_model() if canonical else declaration
            conversion.to_model(datasets=[dataset, dataset])
