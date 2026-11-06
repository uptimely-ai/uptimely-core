"""Direct raising-rule contracts against a complete example spec."""

import dataclasses
import json
import logging
import pathlib
import types

import pytest
from support import examples as example_support

from uptimely import spec
from uptimely.spec import functions as function_kinds
from uptimely.spec.validation import errors
from uptimely.spec.validation import spec as spec_validation
from uptimely.spec.validation.rules import functions
from uptimely.spec.validation.rules.actions import contracts as action_contracts
from uptimely.spec.validation.rules.actions import outputs as action_outputs


@pytest.mark.parametrize(
    "validate",
    [*spec_validation.VALIDATION_DEPENDENCIES, action_outputs.warn_unproduced_features],
    ids=lambda validate: f"{validate.__module__.rsplit('.', 1)[-1]}.{validate.__name__}",
)
def test_each_spec_rule_logs_its_check(
    document: spec.Spec,
    caplog: pytest.LogCaptureFixture,
    validate: spec_validation.Validator,
) -> None:
    caplog.set_level(logging.DEBUG, logger="uptimely.spec.validation")

    validate(document)

    assert len(caplog.records) == 1
    assert caplog.messages[0].startswith("    - checking ")
    assert caplog.records[0].levelno == logging.DEBUG
    assert caplog.records[0].name == validate.__module__


@pytest.mark.parametrize("level", [logging.DEBUG, logging.INFO])
def test_spec_validation_logs_heading_and_all_checks_only_at_debug(
    document: spec.Spec,
    caplog: pytest.LogCaptureFixture,
    level: int,
) -> None:
    caplog.set_level(level, logger="uptimely.spec.validation")

    spec_validation.validate_spec(document)

    if level == logging.INFO:
        assert not caplog.records
        return
    assert caplog.messages[0] == "  Semantic checks:"
    assert len(caplog.messages) == len(spec_validation.VALIDATION_DEPENDENCIES) + 2
    assert all(message.startswith("    - checking ") for message in caplog.messages[1:])
    assert caplog.messages[-1] == ("    - checking declared features have producers (warning only)")
    assert all(record.levelno == logging.DEBUG for record in caplog.records)


def test_failed_spec_validation_logs_the_failing_check_before_stopping(
    document: spec.Spec, caplog: pytest.LogCaptureFixture
) -> None:
    document.operator_items[0][1].compute.function = "missing_function"
    caplog.set_level(logging.DEBUG, logger="uptimely.spec.validation")

    with pytest.raises(errors.SpecError) as error:
        spec_validation.validate_spec(document)

    assert error.value.code == "unknown_function_reference"
    assert caplog.messages[-1] == "    - checking action function references"
    assert (
        "    - checking binding argument names match function declarations" not in caplog.messages
    )
    assert not any("warning only" in message for message in caplog.messages)


@pytest.fixture
def document(example_projects: pathlib.Path) -> spec.Spec:
    return spec.Spec.model_validate(
        json.loads(
            (example_support.EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json").read_text(
                encoding="utf-8"
            )
        )
    )


@pytest.mark.parametrize("use_runner", [False, True])
def test_unknown_function_error_uses_declaration_path(
    document: spec.Spec, use_runner: bool
) -> None:
    key, item = document.operator_items[0]
    item.compute.function = "missing_function"
    validate = (
        spec_validation.validate_spec if use_runner else action_outputs.validate_function_reference
    )
    with pytest.raises(errors.SpecError) as error:
        validate(document)
    assert error.value.code == "unknown_function_reference"
    assert error.value.path == (*document.declaration_paths[key], "compute", "function")
    assert "missing_function" in str(error.value)


def test_function_rules_raise_independently(document: spec.Spec) -> None:
    function = next(f for f in document.functions.root.values() if f.kind == "vectorize")
    function.returns = "none"
    assert functions.validate_dataframe_count(document) is None
    with pytest.raises(errors.SpecError) as error:
        functions.validate_return_kind(document)
    assert error.value.code == "invalid_function_return_contract"
    assert "fit kind(s): write" in str(error.value)

    function.returns = "dataframe"
    function.args.clear()
    document = spec.Spec.model_validate(document.model_dump())
    assert functions.validate_return_kind(document) is None
    with pytest.raises(errors.SpecError) as error:
        functions.validate_dataframe_count(document)
    assert error.value.code == "invalid_function_input_contract"


@pytest.mark.parametrize("kind", ["conform", "collapse", "expand"])
def test_mapping_rules_use_shared_operation_dataframe_counts(
    document: spec.Spec, monkeypatch: pytest.MonkeyPatch, kind: function_kinds.FunctionKindId
) -> None:
    function = next(f for f in document.functions.root.values() if f.kind == "collapse")
    function.kind = kind
    definitions = dict(function_kinds.FUNCTION_KINDS)
    definitions[kind] = dataclasses.replace(definitions[kind], dataframe_inputs=2)
    monkeypatch.setattr(function_kinds, "FUNCTION_KINDS", types.MappingProxyType(definitions))

    with pytest.raises(errors.SpecError, match=r"exactly 2 foreign profile\(s\)") as error:
        action_contracts.validate_dataset_argument_count(document)
    assert error.value.code == "invalid_mapping_dataset_input"
    assert error.value.path[-2:] == ("compute", "args")


def test_local_and_foreign_input_validation_uses_kind_attributes(
    document: spec.Spec, monkeypatch: pytest.MonkeyPatch
) -> None:
    vectorize = next(
        item
        for item in document.actions
        if document.functions[item.compute.function].kind == "vectorize"
    )
    definitions = dict(function_kinds.FUNCTION_KINDS)
    definitions["vectorize"] = dataclasses.replace(
        definitions["vectorize"], dataframe_input_scope="foreign"
    )
    monkeypatch.setattr(function_kinds, "FUNCTION_KINDS", types.MappingProxyType(definitions))

    with pytest.raises(errors.SpecError, match="must reference a foreign source profile"):
        action_contracts.validate_foreign_dataset_argument(document)

    assert document.functions[vectorize.compute.function].kind == "vectorize"


def test_target_dataset_validation_uses_kind_attribute(
    document: spec.Spec, monkeypatch: pytest.MonkeyPatch
) -> None:
    definitions = dict(function_kinds.FUNCTION_KINDS)
    definitions["collapse"] = dataclasses.replace(
        definitions["collapse"], dataframe_input_scope="target"
    )
    monkeypatch.setattr(function_kinds, "FUNCTION_KINDS", types.MappingProxyType(definitions))

    with pytest.raises(errors.SpecError, match="must consume its target profile"):
        action_contracts.validate_target_dataset_input(document)


def test_feature_input_validation_uses_kind_attribute(
    document: spec.Spec, monkeypatch: pytest.MonkeyPatch
) -> None:
    definitions = dict(function_kinds.FUNCTION_KINDS)
    definitions["vectorize"] = dataclasses.replace(
        definitions["vectorize"], feature_input_scope="none"
    )
    monkeypatch.setattr(function_kinds, "FUNCTION_KINDS", types.MappingProxyType(definitions))

    with pytest.raises(errors.SpecError, match="Kind vectorize cannot declare feature inputs"):
        action_contracts.validate_feature_input_scope(document)


def test_none_dataframe_input_count_is_unrestricted(document: spec.Spec) -> None:
    escape = next(
        function for function in document.functions.root.values() if function.kind == "escape"
    )
    escape.args = {
        "first": spec.Argument(id="first", type="dataframe"),
        "second": spec.Argument(id="second", type="dataframe"),
    }

    assert functions.validate_dataframe_count(document) is None
