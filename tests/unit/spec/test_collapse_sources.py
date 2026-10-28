import json
from unittest import mock

import pytest
from conftest import EXAMPLES_ROOT

from uptimely import row_context, spec
from uptimely.spec import references, selectors, validation
from uptimely.spec.validation import collapse_inputs, context

SPEC_PATH = EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json"


@pytest.mark.parametrize(
    "inputs",
    [
        [],
        ["$features.pump"],
        ["$features.missing"],
        ["$features.bearing_temperature", "$features.health_signal_normalized"],
        ["$features.bearing_temperature"],
    ],
)
@pytest.mark.parametrize("ambiguous", [False, True])
def test_collapse_source_is_prepared_from_indexed_feature_owners(
    inputs: list[str], ambiguous: bool
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["entities"]["pump"]["datasets"]["pump_dataset"]["actions"][
        "bearing_temperature_by_pump"
    ]["features"]["inputs"] = inputs
    document = spec.Spec.model_validate(configuration)
    if ambiguous:
        dataset = document.entities["pump_telemetry"].datasets["pump_telemetry_dataset"]
        document.entities["pump"].datasets[dataset.id] = dataset.model_copy(deep=True)
    action = (
        document.entities["pump"].datasets["pump_dataset"].actions["bearing_temperature_by_pump"]
    )
    index = context.SpecValidationContext.build(document)
    prepared = next(item for item in index.collapse_inputs if item.action.location.action is action)
    results = [
        collapse_inputs.validate_source_feature(prepared),
        *(
            collapse_inputs.validate_feature_owner(action.id, feature, candidates)
            for feature, candidates in prepared.candidates
        ),
        collapse_inputs.validate_source_count(prepared),
    ]
    prepared_error = next((error for error in results if error is not None), None)

    if prepared_error is not None:
        assert prepared.source is None
    else:
        assert prepared.source is not None
        assert any(
            prepared.source in index.feature_owners.get(feature, ())
            for feature in action.input_features
            if feature != selectors.CURRENT_ID and feature not in document.dimensions
        )
        assert index.collapse_sources[prepared.action.location.key] is prepared.source


@pytest.mark.parametrize("with_row_context", [False, True])
def test_validation_prepares_collapse_sources_once_per_invocation(
    with_row_context: bool,
) -> None:
    document = spec.Spec.model_validate(json.loads(SPEC_PATH.read_text(encoding="utf-8")))
    if with_row_context:
        action = (
            document.entities["pump"]
            .datasets["pump_dataset"]
            .actions["bearing_temperature_by_pump"]
        )
        action.row_context = row_context.RowContext(
            dimension="$dimensions.timestamp",
            before=row_context.ContextExtent(time="1h"),
        )
    expected = sum(
        document.functions[action.binding.function].kind == "collapse"
        for _, _, action in references.iter_actions(document)
    )
    assert expected > 0

    with mock.patch.object(
        context.SpecValidationContext,
        "_prepare_collapse_inputs",
        autospec=True,
        side_effect=context.SpecValidationContext._prepare_collapse_inputs,
    ) as prepare:
        validation.validate_spec(document)
        assert prepare.call_count == 1
        validation.validate_spec(document)
        assert prepare.call_count == 2
