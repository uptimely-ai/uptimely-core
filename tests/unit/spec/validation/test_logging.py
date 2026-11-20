import json
import logging
import pathlib

import pydantic
import pytest
from support import examples as example_support

from uptimely import spec
from uptimely.spec import model

SPEC_PATH = example_support.EXAMPLES_ROOT / "artifacts/build/spec.json"


def test_loading_can_suppress_structure_debug_without_disabling_checks(
    tmp_path: pathlib.Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger="uptimely.spec")
    path = tmp_path / "spec.json"
    path.write_text("{}", encoding="utf-8")

    spec.load_spec(path, log_structure=False)

    assert "Check spec version is an integer" not in caplog.messages
    assert "Check globally unique profile IDs" in caplog.messages
    caplog.clear()
    path.write_text('{"spec_version": true}', encoding="utf-8")
    with pytest.raises(ValueError, match="spec_version must be an integer"):
        spec.load_spec(path, log_structure=False)
    assert not caplog.records


def test_document_structure_checks_emit_flat_debug_messages(
    caplog: pytest.LogCaptureFixture,
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    profiles = list(configuration["profiles"].values())
    operator_count = sum(len(profile["assembly"]) for profile in profiles)
    caplog.set_level(logging.DEBUG, logger="uptimely.spec.model")

    spec.Spec.model_validate(configuration)

    assert caplog.messages == [
        f"Check object keys as identifiers for {len(profiles)} profiles",
        "Check spec version is an integer",
        f"Check feature references for {operator_count} operators",
    ]
    assert all(record.levelno == logging.DEBUG for record in caplog.records)


def test_loading_logs_flat_checks_once_in_validation_order(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="uptimely.spec")

    spec.load_spec(SPEC_PATH)

    assert caplog.messages.count("Check spec version is an integer") == 1
    assert caplog.messages.count("Check globally unique profile IDs") == 1
    assert all(
        "\n" not in message and message == message.lstrip() and not message.endswith(":")
        for message in caplog.messages
    )
    assert caplog.messages.index("Check globally unique profile IDs") > caplog.messages.index(
        "Check spec version is an integer"
    )


def test_invalid_operator_reference_does_not_repeat_document_checks(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="uptimely.spec.model")

    with pytest.raises(pydantic.ValidationError, match=r"\$features"):
        model.Interface(inputs=["invalid"])

    assert not caplog.messages


@pytest.mark.parametrize("level", [logging.DEBUG, logging.INFO])
def test_structure_summary_counts_profiles_and_operator_once(
    caplog: pytest.LogCaptureFixture, level: int
) -> None:
    configuration = {
        "spec_version": 9,
        "profiles": {
            "profile_1": {
                "name": "First",
                "assembly": {
                    f"operator_{operator}": {"compute": {"function": "read"}}
                    for operator in range(8)
                },
            },
            "profile_2": {
                "name": "Second",
                "assembly": {
                    f"operator_{operator}": {"compute": {"function": "read"}}
                    for operator in range(5)
                },
            },
            "profile_3": {
                "name": "Third",
                "assembly": {
                    f"operator_{operator}": {"compute": {"function": "read"}}
                    for operator in range(7)
                },
            },
        },
    }
    caplog.set_level(level, logger="uptimely.spec.model")

    spec.Spec.model_validate(configuration)

    assert caplog.messages == (
        [
            "Check object keys as identifiers for 3 profiles",
            "Check spec version is an integer",
            "Check feature references for 20 operators",
        ]
        if level == logging.DEBUG
        else []
    )


def test_structure_summary_counts_existing_resource_models(
    caplog: pytest.LogCaptureFixture,
) -> None:
    document = spec.Spec.model_validate_json(SPEC_PATH.read_text(encoding="utf-8"))
    profile_count = len(document.profile_items)
    operator_count = len(document.operators)
    caplog.set_level(logging.DEBUG, logger="uptimely.spec.model")

    spec.Spec.model_validate({"profiles": document.profiles})

    assert caplog.messages == [
        f"Check object keys as identifiers for {profile_count} profiles",
        "Check spec version is an integer",
        f"Check feature references for {operator_count} operators",
    ]


@pytest.mark.parametrize(
    "configuration",
    [
        {"profiles": ["invalid"]},
        {"profiles": {"profile": None}},
        {"profiles": {"profile": {"unknown": True}}},
        {"profiles": {"profile": {"assembly": {"operator": ["invalid"]}}}},
    ],
)
def test_structure_summary_preserves_invalid_document_errors(
    caplog: pytest.LogCaptureFixture, configuration: dict[str, object]
) -> None:
    with pytest.raises(pydantic.ValidationError) as original:
        spec.Spec.model_validate(configuration)
    caplog.set_level(logging.DEBUG, logger="uptimely.spec.model")

    with pytest.raises(pydantic.ValidationError) as logged:
        spec.Spec.model_validate(configuration)

    assert logged.value.errors() == original.value.errors()
    assert len(caplog.messages) == 3
