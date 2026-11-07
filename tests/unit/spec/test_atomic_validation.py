"""Direct raising-rule contracts against a complete example spec."""

import dataclasses
import json
import logging
import pathlib
import types

import pytest
from support import examples as example_support

from uptimely import spec
from uptimely.spec import function_kinds
from uptimely.spec.validation import errors
from uptimely.spec.validation import spec as spec_validation
from uptimely.spec.validation.rules import bindings, functions
from uptimely.spec.validation.rules.operators import contracts as operator_contracts
from uptimely.spec.validation.rules.operators import outputs as operator_outputs


@pytest.mark.parametrize(
    "validate",
    [*spec_validation.VALIDATION_DEPENDENCIES, operator_outputs.warn_unproduced_features],
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
    assert caplog.messages[-1] == "    - checking compute functions exist"
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
        spec_validation.validate_spec
        if use_runner
        else operator_outputs.validate_compute_function_exists
    )
    with pytest.raises(errors.SpecError) as error:
        validate(document)
    assert error.value.code == "unknown_function_reference"
    assert error.value.path == (*document.declaration_paths[key], "compute", "function")
    assert "missing_function" in str(error.value)


def test_unknown_merge_function_error_uses_declaration_path(document: spec.Spec) -> None:
    key, item = document.operator_items[0]
    item.merge = spec.model.Binding(function="missing_merge")

    with pytest.raises(errors.SpecError) as error:
        operator_outputs.validate_merge_function_exists(document)

    assert error.value.code == "unknown_function_reference"
    assert error.value.path == (*document.declaration_paths[key], "merge", "function")
    assert "missing_merge" in str(error.value)


def test_compute_function_kind_is_validated_independently(document: spec.Spec) -> None:
    key, operator = document.operator_items[0]
    document.functions.root[operator.compute.function].kind = function_kinds.MERGE

    with pytest.raises(errors.SpecError, match="must be declared in Operator.merge") as error:
        operator_outputs.validate_compute_function_kind(document)

    assert error.value.code == "invalid_merge_binding"
    assert error.value.path == (*document.declaration_paths[key], "compute", "function")


def test_merge_binding_rejects_non_merge_function(document: spec.Spec) -> None:
    _, item = document.operator_items[0]
    item.merge = spec.model.Binding(function=item.compute.function)

    with pytest.raises(errors.SpecError, match="function of kind 'merge'"):
        operator_outputs.validate_merge_function_kind(document)


def _add_merge_binding(document: spec.Spec) -> spec.model.Operator:
    _, operator = document.operator_items[0]
    document.functions.root["merge"] = spec.model.FunctionTemplate(
        id="merge",
        kind="merge",
        returns="dataframe",
        entrypoint="merge",
        validate_signature=False,
        args={
            "target": spec.model.Argument(id="target", type="dataframe | null"),
            "fragment": spec.model.Argument(id="fragment", type="dataframe"),
        },
    )
    operator.merge = spec.model.Binding(
        function="merge",
        args={
            "target": "$profiles.@.dataframe",
            "fragment": "$operators.@.fragment",
        },
    )
    return operator


def test_merge_operator_kind_is_validated_independently(document: spec.Spec) -> None:
    operator = _add_merge_binding(document)
    document.functions.root[operator.compute.function].kind = "vectorize"

    with pytest.raises(errors.SpecError, match="Vectorize operators cannot declare") as error:
        bindings.validate_merge_operator_kind(document)

    assert error.value.code == "invalid_merge_binding"


def test_merge_target_is_validated_independently(document: spec.Spec) -> None:
    operator = _add_merge_binding(document)
    operator.merge.args["target"] = spec.model.BindingArgument("$profiles.other.dataframe")

    with pytest.raises(errors.SpecError, match="current profile dataframe") as error:
        bindings.validate_merge_target(document)

    assert error.value.code == "invalid_merge_binding"
    assert error.value.path[-3:] == ("merge", "args", "target")


def test_merge_fragment_is_validated_independently(document: spec.Spec) -> None:
    operator = _add_merge_binding(document)
    operator.merge.args["fragment"] = spec.model.BindingArgument("$operators.other.fragment")

    with pytest.raises(errors.SpecError, match="staged fragment") as error:
        bindings.validate_merge_fragment(document)

    assert error.value.code == "invalid_merge_binding"
    assert error.value.path[-3:] == ("merge", "args", "fragment")


def test_merge_feature_references_are_validated_independently(document: spec.Spec) -> None:
    operator = _add_merge_binding(document)
    operator.merge.args["feature"] = spec.model.BindingArgument("$features.value")

    with pytest.raises(errors.SpecError, match="cannot reference features") as error:
        bindings.validate_merge_feature_references(document)

    assert error.value.code == "invalid_merge_feature_reference"


def test_selector_metadata_is_validated_independently(document: spec.Spec) -> None:
    key, operator = document.operator_items[0]
    function = document.functions.root[operator.compute.function]
    function.args["metadata"] = spec.model.Argument(id="metadata", type="object{str: string}")
    operator.compute.args["metadata"] = spec.model.BindingArgument(
        {"nested": "$dimensions.missing.name"}
    )

    with pytest.raises(errors.SpecError, match="Cannot resolve resource metadata") as error:
        bindings.validate_selector_metadata(document)

    assert error.value.code == "invalid_binding_selector"
    assert error.value.path == (
        *document.declaration_paths[key],
        "compute",
        "args",
        "metadata",
        "nested",
    )


def _add_merge_function(document: spec.Spec) -> spec.model.FunctionTemplate:
    function = spec.model.FunctionTemplate(
        id="merge",
        kind="merge",
        returns="dataframe",
        entrypoint="merge",
        validate_signature=False,
        args={
            "target": spec.model.Argument(id="target", type="dataframe | null"),
            "fragment": spec.model.Argument(id="fragment", type="dataframe"),
        },
    )
    document.functions.root[function.id] = function
    return function


def test_nullable_dataframe_argument_is_rejected_for_non_merge_function(
    document: spec.Spec,
) -> None:
    function = next(
        function
        for function in document.functions.root.values()
        if function.kind != function_kinds.MERGE
    )
    function.args["nullable"] = spec.model.Argument(id="nullable", type="dataframe | null")

    with pytest.raises(errors.SpecError, match="reserved for merge functions") as error:
        functions.validate_nullable_dataframe_arguments(document)

    assert error.value.code == "invalid_function_input_contract"


def test_merge_target_argument_is_validated_independently(document: spec.Spec) -> None:
    function = _add_merge_function(document)
    function.args["target"].type = "dataframe"

    with pytest.raises(errors.SpecError, match="target as 'dataframe \\| null'") as error:
        functions.validate_merge_target_argument(document)

    assert error.value.code == "invalid_function_input_contract"


def test_merge_fragment_argument_is_validated_independently(document: spec.Spec) -> None:
    function = _add_merge_function(document)
    function.args["fragment"].type = "string"

    with pytest.raises(errors.SpecError, match="fragment as 'dataframe'") as error:
        functions.validate_merge_fragment_argument(document)

    assert error.value.code == "invalid_function_input_contract"


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
        operator_contracts.validate_dataset_argument_count(document)
    assert error.value.code == "invalid_mapping_dataset_input"
    assert error.value.path[-2:] == ("compute", "args")


def test_local_and_foreign_input_validation_uses_kind_attributes(
    document: spec.Spec, monkeypatch: pytest.MonkeyPatch
) -> None:
    vectorize = next(
        item
        for item in document.operators
        if document.functions[item.compute.function].kind == "vectorize"
    )
    definitions = dict(function_kinds.FUNCTION_KINDS)
    definitions["vectorize"] = dataclasses.replace(
        definitions["vectorize"], dataframe_input_scope="foreign"
    )
    monkeypatch.setattr(function_kinds, "FUNCTION_KINDS", types.MappingProxyType(definitions))

    with pytest.raises(errors.SpecError, match="must reference a foreign source profile"):
        operator_contracts.validate_foreign_dataset_argument(document)

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
        operator_contracts.validate_target_dataset_input(document)


def test_feature_input_validation_uses_kind_attribute(
    document: spec.Spec, monkeypatch: pytest.MonkeyPatch
) -> None:
    definitions = dict(function_kinds.FUNCTION_KINDS)
    definitions["vectorize"] = dataclasses.replace(
        definitions["vectorize"], feature_input_scope="none"
    )
    monkeypatch.setattr(function_kinds, "FUNCTION_KINDS", types.MappingProxyType(definitions))

    with pytest.raises(errors.SpecError, match="Kind vectorize cannot declare feature inputs"):
        operator_contracts.validate_feature_input_scope(document)


def test_none_dataframe_input_count_is_unrestricted(document: spec.Spec) -> None:
    escape = next(
        function for function in document.functions.root.values() if function.kind == "escape"
    )
    escape.args = {
        "first": spec.Argument(id="first", type="dataframe"),
        "second": spec.Argument(id="second", type="dataframe"),
    }

    assert functions.validate_dataframe_count(document) is None
