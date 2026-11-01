"""Collapse source indexes retain invalid declarations without wrapper objects."""

import json

import pytest
from support import examples as example_support

from uptimely import spec
from uptimely.spec import validation
from uptimely.spec.validation.rules.actions import inputs as action_inputs

SPEC_PATH = example_support.EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json"
pytestmark = pytest.mark.usefixtures("example_projects")


@pytest.mark.parametrize(
    ("inputs", "message"),
    [
        ([], "must reference a source feature"),
        (["$features.pump"], "must reference a source feature"),
        (["$features.missing"], "unknown input feature"),
        (
            ["$features.bearing_temperature", "$features.health_signal_normalized"],
            "must belong to one dataset",
        ),
        (["$features.bearing_temperature"], None),
    ],
)
@pytest.mark.parametrize("ambiguous", [False, True])
def test_collapse_source_discovery_retains_invalid_candidates(
    inputs: list[str], message: str | None, ambiguous: bool
) -> None:
    document = spec.Spec.model_validate(json.loads(SPEC_PATH.read_text(encoding="utf-8")))
    action = (
        document.entities["pump"].datasets["pump_dataset"].actions["bearing_temperature_by_pump"]
    )
    action.features.inputs = inputs
    if ambiguous:
        dataset = document.entities["pump_telemetry"].datasets["pump_telemetry_dataset"]
        document.entities["pump"].datasets[dataset.id] = dataset.model_copy(deep=True)
        if "$features.bearing_temperature" in inputs:
            message = "ambiguous input feature"
    original = document.model_copy(deep=True)
    facts = document.input_sources
    key = ("pump", "pump_dataset", "bearing_temperature_by_pump")
    source = facts[key]

    def validate_source() -> None:
        action_inputs.validate_source_feature(document)
        action_inputs.validate_feature_owner(document)
        action_inputs.validate_source_count(document)

    if message is not None:
        with pytest.raises(ValueError, match=message):
            validate_source()
        assert source is None
    else:
        validate_source()
        assert source is not None
        owners = document.feature_owners
        assert any(source in owners.get(feature, ()) for feature in action.input_features)
        assert document.actions_by_key[key] is action
    assert document == original


def test_new_document_rediscovers_collapse_sources_after_edits() -> None:
    document = spec.Spec.model_validate(json.loads(SPEC_PATH.read_text(encoding="utf-8")))
    validation.validate_spec(document)
    action = (
        document.entities["pump"].datasets["pump_dataset"].actions["bearing_temperature_by_pump"]
    )
    key = ("pump", "pump_dataset", "bearing_temperature_by_pump")
    first = document.input_sources[key]
    assert first is not None
    assert first[1] == "pump_telemetry_dataset"
    target = document.entities["pump"].datasets["pump_dataset"]
    target.features["local_source"] = spec.Feature(id="local_source")
    action.features.inputs = ["$features.local_source"]
    document = spec.Spec.model_validate(document.model_dump())
    second = document.input_sources[key]
    assert second is not None
    assert second[1] == "pump_dataset"
    with pytest.raises(ValueError, match="cannot use its target dataset as source"):
        validation.validate_spec(document)
