import json
from unittest import mock

import pytest
from conftest import EXAMPLES_ROOT

from uptimely import row_context, spec
from uptimely.spec import references, validation
from uptimely.spec.validation import context

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
    configuration["entities"]["pump"]["datasets"][0]["mappings"]["bearing_temperature_by_pump"][
        "features"
    ]["inputs"] = inputs
    document = spec.Spec.model_validate(configuration)
    if ambiguous:
        dataset = document.entities["pump_telemetry"].datasets[0]
        document.entities["pump_telemetry"].datasets.append(dataset.model_copy(deep=True))
    mapping = document.entities["pump"].datasets[0].mappings["bearing_temperature_by_pump"]
    index = context.SpecValidationContext.build(document)
    owners = {
        feature_id: [(owner.entity, owner.dataset) for owner in candidates]
        for feature_id, candidates in index.feature_owners.items()
    }

    try:
        expected = references.collapse_input_dataset(document, mapping)
    except ValueError as expected_error:
        with pytest.raises(type(expected_error)) as actual:
            references.collapse_input_dataset(document, mapping, feature_owners=owners)
        assert str(actual.value) == str(expected_error)
    else:
        actual_source = references.collapse_input_dataset(document, mapping, feature_owners=owners)
        assert actual_source[0] is expected[0]
        assert actual_source[1] is expected[1]


@pytest.mark.parametrize("with_row_context", [False, True])
def test_validation_resolves_each_collapse_source_once_per_invocation(
    with_row_context: bool,
) -> None:
    document = spec.Spec.model_validate(json.loads(SPEC_PATH.read_text(encoding="utf-8")))
    if with_row_context:
        mapping = document.entities["pump"].datasets[0].mappings["bearing_temperature_by_pump"]
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
        references, "collapse_input_dataset", wraps=references.collapse_input_dataset
    ) as resolve:
        validation.validate_spec(document)
        assert resolve.call_count == expected
        validation.validate_spec(document)
        assert resolve.call_count == 2 * expected
