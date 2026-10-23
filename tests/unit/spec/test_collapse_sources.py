import json
from unittest import mock

import pytest
from conftest import EXAMPLES_ROOT

from uptimely import row_context, spec
from uptimely.spec import references, validation
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
def test_indexed_source_resolution_matches_document_scan(
    inputs: list[str], ambiguous: bool
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["entities"]["pump"]["datasets"]["pump_dataset"]["mappings"][
        "bearing_temperature_by_pump"
    ]["features"]["inputs"] = inputs
    document = spec.Spec.model_validate(configuration)
    if ambiguous:
        dataset = document.entities["pump_telemetry"].datasets["pump_telemetry_dataset"]
        document.entities["pump"].datasets[dataset.id] = dataset.model_copy(deep=True)
    mapping = (
        document.entities["pump"].datasets["pump_dataset"].mappings["bearing_temperature_by_pump"]
    )
    index = context.SpecValidationContext.build(document)
    owners = {
        feature_id: [(owner.entity, owner.dataset) for owner in candidates]
        for feature_id, candidates in index.feature_owners.items()
    }
    prepared = next(
        item for item in index.collapse_inputs if item.mapping.location.mapping is mapping
    )
    results = [
        collapse_inputs.validate_source_feature(prepared),
        *(
            collapse_inputs.validate_feature_owner(mapping.id, feature, candidates)
            for feature, candidates in prepared.candidates
        ),
        collapse_inputs.validate_source_count(prepared),
    ]
    prepared_error = next((error for error in results if error is not None), None)

    try:
        expected = references.collapse_input_dataset(document, mapping)
    except ValueError as expected_error:
        with pytest.raises(type(expected_error)) as actual:
            references.collapse_input_dataset(document, mapping, feature_owners=owners)
        assert str(actual.value) == str(expected_error)
        assert type(prepared_error) is type(expected_error)
        assert str(prepared_error) == str(expected_error)
    else:
        actual_source = references.collapse_input_dataset(document, mapping, feature_owners=owners)
        assert actual_source[0] is expected[0]
        assert actual_source[1] is expected[1]
        assert prepared_error is None
        dataset_id = document.entities["pump"].datasets["pump_dataset"].id
        source = index.collapse_sources[("pump", dataset_id, mapping.id)]
        assert source.entity is expected[0]
        assert source.dataset is expected[1]


@pytest.mark.parametrize("with_row_context", [False, True])
def test_validation_prepares_collapse_sources_once_per_invocation(
    with_row_context: bool,
) -> None:
    document = spec.Spec.model_validate(json.loads(SPEC_PATH.read_text(encoding="utf-8")))
    if with_row_context:
        mapping = (
            document.entities["pump"]
            .datasets["pump_dataset"]
            .mappings["bearing_temperature_by_pump"]
        )
        mapping.row_context = row_context.RowContext(
            dimension="$dimensions.timestamp",
            before=row_context.ContextExtent(time="1h"),
        )
    expected = sum(
        document.functions[mapping.binding.function].operation == "collapse"
        for _, _, mapping in references.iter_mappings(document)
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
