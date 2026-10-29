"""Collapse source discovery reflects current declarations without cached context."""

import json

import pytest
from conftest import EXAMPLES_ROOT

from uptimely import spec
from uptimely.spec import validation
from uptimely.spec.validation import collapse_inputs, traversal

SPEC_PATH = EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json"


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
    facts = tuple(collapse_inputs.iter_collapse_inputs(document))
    item = next(item for item in facts if item.action.location.action is action)

    def validate_source() -> None:
        collapse_inputs.validate_source_feature(document)
        collapse_inputs.validate_feature_owner(document)
        collapse_inputs.validate_source_count(document)

    if message is not None:
        with pytest.raises(ValueError, match=message):
            validate_source()
        assert item.source is None
    else:
        validate_source()
        assert item.source is not None
        owners = traversal.feature_owners(document)
        assert any(item.source in owners.get(feature, ()) for feature in action.input_features)
        assert collapse_inputs.source_index(facts)[item.action.location.key] is item.source
    assert document == original


def test_revalidation_rediscovers_collapse_sources_after_edits() -> None:
    document = spec.Spec.model_validate(json.loads(SPEC_PATH.read_text(encoding="utf-8")))
    validation.validate_spec(document)
    action = (
        document.entities["pump"].datasets["pump_dataset"].actions["bearing_temperature_by_pump"]
    )
    first = next(
        item
        for item in collapse_inputs.iter_collapse_inputs(document)
        if item.action.location.action is action
    )
    assert first.source is not None
    assert first.source.dataset.id == "pump_telemetry_dataset"
    target = document.entities["pump"].datasets["pump_dataset"]
    target.features["local_source"] = spec.Feature(id="local_source")
    action.features.inputs = ["$features.local_source"]
    second = next(
        item
        for item in collapse_inputs.iter_collapse_inputs(document)
        if item.action.location.action is action
    )
    assert second.source is not None
    assert second.source.dataset.id == "pump_dataset"
    with pytest.raises(ValueError, match="cannot use its target dataset as source"):
        validation.validate_spec(document)
