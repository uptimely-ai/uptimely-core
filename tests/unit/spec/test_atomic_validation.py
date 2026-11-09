"""Direct raising-rule contracts against a complete example spec."""

import json
import logging
import pathlib

import pytest
from support import examples as example_support

from uptimely import spec
from uptimely.spec.validation import errors
from uptimely.spec.validation import spec as spec_validation
from uptimely.spec.validation.rules import bindings, dimensions, profiles
from uptimely.spec.validation.rules.operators import contracts as operator_contracts
from uptimely.spec.validation.rules.operators import inputs as operator_inputs
from uptimely.spec.validation.rules.operators import outputs as operator_outputs


@pytest.mark.parametrize(
    "validate",
    [
        *(validate for _, group in spec_validation.VALIDATION_GROUPS for validate in group),
    ],
    ids=lambda validate: f"{validate.__module__.rsplit('.', 1)[-1]}.{validate.__name__}",
)
def test_each_spec_rule_logs_its_check(
    document: spec.Spec,
    caplog: pytest.LogCaptureFixture,
    validate: spec_validation.Validator,
) -> None:
    caplog.set_level(logging.DEBUG, logger="uptimely.spec.validation")

    validate(document)

    assert caplog.records
    assert all(message.startswith("Check ") for message in caplog.messages)
    assert all(record.levelno == logging.DEBUG for record in caplog.records)
    assert all(record.name == validate.__module__ for record in caplog.records)


@pytest.mark.parametrize(
    ("validate", "reference", "message"),
    [
        (
            operator_inputs.validate_profile_reference,
            "$profiles.missing.dataset",
            "Check referenced profile missing for spec operator compute in target profile target",
        ),
        (
            operator_inputs.validate_feature_reference,
            "$features.missing",
            "Check feature selector missing for spec operator compute in target profile target",
        ),
        (
            operator_inputs.validate_dimension_reference,
            "$dimensions.missing.id",
            "Check referenced dimension missing for spec operator compute in target profile target",
        ),
    ],
)
def test_operator_reference_log_identifies_resource_before_failure(
    caplog: pytest.LogCaptureFixture,
    validate: spec_validation.Validator,
    reference: str,
    message: str,
) -> None:
    document = spec.Spec.model_validate(
        {
            "profiles": {
                "target": {
                    "assembly": {
                        "compute": {
                            "compute": {"function": "calculate", "args": {"data": reference}}
                        }
                    }
                }
            }
        }
    )
    caplog.set_level(logging.DEBUG, logger="uptimely.spec.validation")

    with pytest.raises(ValueError, match="unknown"):
        validate(document)

    assert caplog.messages[-1] == message


def test_dimension_and_grain_logs_identify_resources(
    caplog: pytest.LogCaptureFixture,
) -> None:
    document = spec.Spec.model_validate(
        {
            "dimensions": {
                "machine": {
                    "resolutions": {
                        "pump": {"key": "pump_id", "type": "string", "parent": "fleet"},
                        "fleet": {"key": "fleet_id", "type": "string"},
                    }
                }
            },
            "profiles": {
                "telemetry": {"grain": [{"dimension": "machine", "resolution": "pump"}]},
                "summary": {"grain": [{"dimension": "machine", "resolution": "fleet"}]},
            },
        }
    )
    caplog.set_level(logging.DEBUG, logger="uptimely.spec.validation")

    dimensions.validate_parent(document)
    dimensions.validate_parent_cycle(document)
    profiles.validate_grain_dimensions(document)
    profiles.validate_grain_resolutions(document)
    profiles.validate_unique_grain_dimensions(document)
    profiles.validate_unique_grain_keys(document)

    assert "Check parent resolution fleet for spec dimension machine, resolution pump" in (
        caplog.messages
    )
    for resolution in ("pump", "fleet"):
        assert (
            f"Check parent chain for spec dimension machine, resolution {resolution}"
            in caplog.messages
        )
    for profile, resolution in (("telemetry", "pump"), ("summary", "fleet")):
        assert f"Check grain dimension machine for spec profile {profile}" in caplog.messages
        assert (
            f"Check grain resolution {resolution} in dimension machine "
            f"for spec profile {profile}" in caplog.messages
        )
        assert f"Check grain dimension uniqueness for spec profile {profile}" in caplog.messages
        assert f"Check grain dataframe-key uniqueness for spec profile {profile}" in caplog.messages


@pytest.mark.parametrize("level", [logging.DEBUG, logging.INFO])
def test_spec_validation_logs_flat_checks_only_at_debug(
    document: spec.Spec,
    caplog: pytest.LogCaptureFixture,
    level: int,
) -> None:
    caplog.set_level(level, logger="uptimely.spec.validation")

    spec_validation.validate_spec(document)

    assert caplog.messages[-1] == "Spec validated"
    assert caplog.records[-1].levelno == logging.INFO
    if level == logging.INFO:
        assert caplog.messages == ["Start spec validation", "Spec validated"]
        return
    assert caplog.messages[0] == "Start spec validation"
    assert caplog.records[0].levelno == logging.INFO
    assert caplog.messages[1] == "Check globally unique profile IDs"
    assert len(caplog.messages) - 2 >= sum(
        len(checks) for _name, checks in spec_validation.VALIDATION_GROUPS
    )
    assert all(
        message.startswith("Check ") and "\n" not in message for message in caplog.messages[1:-1]
    )
    assert caplog.messages[-2] == "Check declared features have producers (warning only)"
    assert all(record.levelno == logging.DEBUG for record in caplog.records[1:-1])


def test_failed_spec_validation_logs_the_failing_check_before_stopping(
    document: spec.Spec, caplog: pytest.LogCaptureFixture
) -> None:
    document.operator_items[0][1].compute.function = "missing_function"
    caplog.set_level(logging.DEBUG, logger="uptimely.spec.validation")

    with pytest.raises(errors.SpecError) as error:
        spec_validation.validate_spec(document)

    assert error.value.code == "unknown_function_reference"
    assert caplog.messages[0] == "Start spec validation"
    assert caplog.records[0].levelno == logging.INFO
    assert caplog.messages[-1] == "Check compute functions exist"
    assert "Check binding argument names match function declarations" not in caplog.messages
    assert not any("warning only" in message for message in caplog.messages)
    assert "Spec validated" not in caplog.messages


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


def _add_merge_binding(document: spec.Spec) -> spec.model.Operator:
    _, operator = document.operator_items[0]
    document.functions.root["merge"] = spec.model.FunctionTemplate(
        id="merge",
        returns="dataframe",
        entrypoint="merge",
        validate_signature=False,
        args={
            "dataset": spec.model.Argument(id="dataset", type="dataframe | null"),
            "fragment": spec.model.Argument(id="fragment", type="dataframe"),
        },
    )
    operator.merge = spec.model.Binding(
        function="merge",
        args={
            "dataset": "$profiles.@.dataset",
            "fragment": "$operators.@.fragment",
        },
    )
    return operator


def test_merge_binding_requires_two_dataframe_argument_slots(document: spec.Spec) -> None:
    _add_merge_binding(document)
    document.functions["merge"].args.pop("fragment")

    with pytest.raises(errors.SpecError, match="invalid dataframe arity: 1") as error:
        bindings.validate_binding_contracts(document)

    assert error.value.code == "invalid_binding_arity"


def test_compute_dataframe_arity_counts_slots_not_profile_ids(document: spec.Spec) -> None:
    key, operator = document.operator_items[0]
    function = document.functions[operator.compute.function]
    function.args = {
        name: spec.model.Argument(id=name, type="dataframe") for name in ("first", "second")
    }
    operator.compute.args = {
        name: spec.model.BindingArgument("$profiles.target.dataset") for name in ("first", "second")
    }

    with pytest.raises(
        errors.SpecError, match="compute binding has invalid dataframe arity: 2"
    ) as error:
        bindings.validate_binding_contracts(document)

    assert error.value.code == "invalid_binding_arity"
    assert error.value.path == (*document.declaration_paths[key], "compute", "args")


def test_merge_dataset_must_be_nullable_for_initialization(document: spec.Spec) -> None:
    _add_merge_binding(document)
    document.functions["merge"].args["dataset"] = spec.model.Argument(
        id="dataset", type="dataframe"
    )

    with pytest.raises(errors.SpecError, match="dataset must allow null") as error:
        bindings.validate_binding_contracts(document)

    assert error.value.code == "invalid_merge_binding"
    assert error.value.path[-3:] == ("merge", "args", "dataset")


def test_merge_dataset_is_validated_independently(document: spec.Spec) -> None:
    operator = _add_merge_binding(document)
    operator.merge.args["dataset"] = spec.model.BindingArgument("$profiles.other.dataset")

    with pytest.raises(errors.SpecError, match="current profile dataframe") as error:
        bindings.validate_merge_dataset(document)

    assert error.value.code == "invalid_merge_binding"
    assert error.value.path[-3:] == ("merge", "args", "dataset")


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


def test_optional_dataframe_arguments_are_not_tied_to_merge_kind(document: spec.Spec) -> None:
    function = next(iter(document.functions.root.values()))
    function.args["nullable"] = spec.model.Argument(id="nullable", type="dataframe | null")

    assert function.check_dataframe_input_contract() is None


def test_function_contract_rules_are_role_and_arity_based(document: spec.Spec) -> None:
    function = next(iter(document.functions.root.values()))
    function.returns = "invalid"
    with pytest.raises(ValueError, match="Unsupported return contract"):
        function.check_return_contract()

    function.returns = "dataframe"
    function.args.clear()
    function.args.update(
        {
            f"frame_{index}": spec.model.Argument(id=f"frame_{index}", type="dataframe")
            for index in range(3)
        }
    )
    with pytest.raises(ValueError, match="at most two dataframe argument slots"):
        function.check_dataframe_input_contract()


def test_zero_dataframe_no_result_compute_contract_is_valid(document: spec.Spec) -> None:
    _, operator = next((key, item) for key, item in document.operator_items if item.merge is None)
    function = document.functions[operator.compute.function]
    function.returns = "none"
    function.args.clear()
    operator.compute.args.clear()

    assert bindings.validate_binding_contracts(document) is None


def test_dataframe_feature_source_must_match_its_argument_profile(document: spec.Spec) -> None:
    vectorize_key = next(
        key for key, label in document.operator_kinds.items() if label == "vectorize"
    )
    operator = document.operators_by_key[vectorize_key]
    dataframe_argument = next(
        name
        for name, argument in document.functions[operator.compute.function].args.items()
        if argument.type == "dataframe"
    )
    operator.compute.args[dataframe_argument] = spec.model.BindingArgument(
        "$profiles.other.dataset"
    )
    document = document.rebuild()

    with pytest.raises(errors.SpecError, match="must reference its target profile") as error:
        operator_contracts.validate_dataframe_argument_feature_source(document)
    assert error.value.path[-1] == dataframe_argument


def test_feature_inputs_require_a_dataframe_source(document: spec.Spec) -> None:
    vectorize_key = next(
        key for key, label in document.operator_kinds.items() if label == "vectorize"
    )
    operator = document.operators_by_key[vectorize_key]
    function = document.functions[operator.compute.function]
    function.args.clear()
    operator.compute.args.clear()
    document = document.rebuild()

    with pytest.raises(errors.SpecError, match="without a dataframe source"):
        operator_contracts.validate_feature_input_scope(document)


def test_escape_operator_policy_is_derived_from_any_return_role(document: spec.Spec) -> None:
    key = next(key for key, label in document.operator_kinds.items() if label == "escape")
    assert document.functions[document.operators_by_key[key].compute.function].returns == "any"
