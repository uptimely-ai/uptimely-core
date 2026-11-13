import copy
import json
import pathlib

import pytest
from support import examples as example_support

from uptimely import spec
from uptimely.spec import validation
from uptimely.spec.validation.rules import (
    bindings,
    dimensions,
)
from uptimely.spec.validation.rules import features as feature_rules
from uptimely.spec.validation.rules.operators import contracts as contracts_validation
from uptimely.spec.validation.rules.operators import inputs as operator_inputs

SPEC_PATH = example_support.EXAMPLES_ROOT / "_generated/build/spec.json"
pytestmark = pytest.mark.usefixtures("example_projects")


def _configuration() -> dict:
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


def test_document_validation_accepts_valid_document_without_mutation() -> None:
    document = spec.Spec.model_validate(_configuration())
    original = document.model_copy(deep=True)

    assert validation.validate_spec(document) is None
    assert document == original


def test_binding_feature_selectors_do_not_become_input_dependencies() -> None:
    document = spec.Spec.model_validate(_configuration())
    operator = document.profiles["pump_telemetry"].assembly["pressure_flow_efficiency"]
    operator.interface.inputs = []
    operator.compute.args["dependency_hint"] = spec.model.BindingArgument(
        "$features.bearing_temperature"
    )

    facts = next(item for item in document.operators if item is operator)

    assert facts.input_features == []
    assert "bearing_temperature" in [
        feature for feature, _ in facts.compute.references_by_prefix["$features."]
    ]


@pytest.mark.parametrize("load_from_file", [False, True])
@pytest.mark.parametrize(
    ("inputs", "message"),
    [
        ([], "Collapse bearing_temperature_by_pump must reference a source feature"),
        (
            ["$features.missing"],
            "Collapse bearing_temperature_by_pump references unknown input feature: missing",
        ),
        (
            ["$features.health_signal_normalized"],
            "Collapse bearing_temperature_by_pump cannot use its target profile as source",
        ),
        (
            ["$features.bearing_temperature", "$features.health_signal_normalized"],
            "Collapse bearing_temperature_by_pump input features must belong to one profile; "
            "use expand to combine inputs from different profiles",
        ),
    ],
)
def test_collapse_rules_report_their_own_fault_without_validating_bindings(
    tmp_path: pathlib.Path, load_from_file: bool, inputs: list[str], message: str
) -> None:
    configuration = _configuration()
    operator = configuration["profiles"]["pump"]["assembly"]["bearing_temperature_by_pump"]
    operator["interface"]["inputs"] = inputs
    operator["compute"]["args"]["unexpected"] = None
    if load_from_file:
        path = tmp_path / "invalid.json"
        path.write_text(json.dumps(configuration), encoding="utf-8")
        document = spec.Spec.model_validate_json(path.read_text(encoding="utf-8"))
    else:
        document = spec.Spec.model_validate(configuration)
    with pytest.raises(ValueError, match=message):
        operator_inputs.validate_source_feature(document)
        operator_inputs.validate_feature_owner(document)
        operator_inputs.validate_source_count(document)
        operator_inputs.validate_source_target(document)
    with pytest.raises(validation.SpecError, match="unknown arguments: unexpected"):
        bindings.validate_arguments(document)


def test_independent_rules_report_grouping_and_dimension_reference_faults() -> None:
    configuration = _configuration()
    machine_dimension = configuration["dimensions"]["machine_dimension"]
    machine_dimension["resolutions"]["machine_category"]["parent"] = "unselected"
    machine_dimension["resolutions"]["unselected"] = {
        "key": "unselected_id",
        "type": "string",
        "parent": None,
    }
    configuration["profiles"]["pump"]["grain"] = [
        {"dimension": "machine_dimension", "resolution": "unselected"}
    ]
    operator = configuration["profiles"]["pump"]["assembly"]["bearing_temperature_by_pump"]
    operator["compute"]["args"]["unexpected"] = "$dimensions.missing"
    document = spec.Spec.model_validate(configuration)
    with pytest.raises(ValueError, match="grouping keys must exist in source"):
        operator_inputs.validate_grouping_dimensions(document)
    with pytest.raises(validation.SpecError, match="unknown dimension: missing"):
        operator_inputs.validate_dimension_reference(document)


@pytest.mark.parametrize("invalid_binding", [False, True])
def test_binding_and_contract_paths_keep_their_existing_operator_identifiers(
    invalid_binding: bool,
) -> None:
    document = spec.Spec.model_validate(_configuration())
    dataset = document.profiles["pump_telemetry"]
    operator = dataset.assembly.pop("pressure_flow_efficiency")
    dataset.assembly["alias"] = operator
    if invalid_binding:
        operator.compute.args["unexpected"] = spec.model.BindingArgument(None)
        expected_id = "alias"
        expected_code = "invalid_binding_arguments"
        validate = bindings.validate_arguments
    else:
        function = document.functions[operator.compute.function]
        argument = next(name for name, arg in function.args.items() if arg.type == "dataframe")
        operator.compute.args[argument] = spec.model.BindingArgument("$profiles.pump.dataset")
        document.operator_kinds[(dataset.id, "alias")] = "vectorize"
        expected_id = "alias"
        expected_code = "invalid_mapping_dataframe_input"
        validate = contracts_validation.validate_dataframe_argument_feature_source
    with pytest.raises(validation.SpecError) as error:
        validate(document)
    assert error.value.code == expected_code
    assert error.value.path == (
        "profiles",
        dataset.id,
        "assembly",
        expected_id,
        "compute",
        "args",
    ) + (() if invalid_binding else (argument,))


def test_direct_semantic_validation_preserves_profile_identity_error() -> None:
    document = spec.Spec.model_validate(_configuration())
    document.profiles["wrong"] = spec.Profile(id="different")

    with pytest.raises(validation.SpecError) as error:
        validation.validate_spec(document)

    assert str(error.value) == (
        "profiles.wrong: Profile key wrong does not match profile id different"
    )
    assert error.value.code == "invalid_profile_id"
    assert error.value.path == ("profiles", "wrong")


def test_public_standalone_profile_id_validation_rejects_mismatched_keys() -> None:
    document = spec.Spec.model_validate(_configuration())
    document.profiles["wrong"] = spec.Profile(id="different")

    with pytest.raises(validation.SpecError) as error:
        validation.validate_profile_ids(document)

    assert error.value.code == "invalid_profile_id"
    assert error.value.path == ("profiles", "wrong")


def test_duplicate_ids_block_operator_cycle_validation() -> None:
    document = spec.Spec.model_validate(_configuration())
    dataset = document.profiles["pump"]
    document.profiles["wrong"] = spec.Profile(id="different")
    operator = dataset.assembly["health_signal_normalized"]
    operator.interface.inputs.append("$features.health_signal_normalized")
    with pytest.raises(validation.SpecError) as error:
        validation.validate_spec(document)
    assert error.value.code == "invalid_profile_id"


def test_document_validation_rejects_duplicate_output_producers() -> None:
    configuration = _configuration()
    assembly = configuration["profiles"]["pump_telemetry"]["assembly"]
    assembly["duplicate"] = copy.deepcopy(assembly["pressure_flow_efficiency"])
    document = spec.Spec.model_validate(configuration)

    with pytest.raises(ValueError, match="produced by multiple operators"):
        validation.validate_spec(document)


@pytest.mark.parametrize(
    ("argument_type", "argument_value"),
    [
        ("array[string]", ["$features.differential_pressure", "$profiles.@.dataset"]),
        (
            "object{str: string}",
            {"nested": ["$features.differential_pressure", "$profiles.@.dataset"]},
        ),
    ],
)
def test_nested_binding_selectors_preserve_expected_argument_type(
    argument_type: str, argument_value: list[str] | dict[str, list[str]]
) -> None:
    configuration = _configuration()
    function = configuration["functions"]["ratio"]
    function["args"]["numerator_features"]["type"] = argument_type
    binding = configuration["profiles"]["pump_telemetry"]["assembly"]["pressure_flow_efficiency"][
        "compute"
    ]
    binding["args"]["numerator_features"] = argument_value
    model = spec.Spec.model_validate(configuration)

    with pytest.raises(validation.SpecError) as error:
        validation.validate_spec(model)

    assert "nested dataframe reference" in str(error.value)
    assert error.value.code == "invalid_binding_arity"
    assert error.value.path == (
        "profiles",
        "pump_telemetry",
        "assembly",
        "pressure_flow_efficiency",
        "compute",
        "args",
        "numerator_features",
    ) + ((1,) if isinstance(argument_value, list) else ("nested", 1))


def test_binding_argument_name_contract_keeps_structured_error() -> None:
    configuration = _configuration()
    operator = configuration["profiles"]["pump_telemetry"]["assembly"]["pressure_flow_efficiency"]
    operator["compute"]["args"] = {"unexpected": None}
    model = spec.Spec.model_validate(configuration)

    with pytest.raises(validation.SpecError) as error:
        validation.validate_spec(model)

    assert error.value.code == "invalid_binding_arguments"
    assert error.value.path == (
        "profiles",
        "pump_telemetry",
        "assembly",
        "pressure_flow_efficiency",
        "compute",
        "args",
    )
    assert "missing arguments:" in str(error.value)
    assert "unknown arguments: unexpected" in str(error.value)


def test_mapping_dependency_cycle_keeps_its_message() -> None:
    configuration = _configuration()
    operator = configuration["profiles"]["pump_telemetry_by_hour_when_warning"]["assembly"][
        "recommended_flow_rate"
    ]
    operator["interface"]["inputs"].append("$features.recommended_flow_rate")
    model = spec.Spec.model_validate(configuration)

    with pytest.raises(ValueError) as error:
        validation.validate_spec(model)

    assert str(error.value) == (
        "Operator feature dependency cycle: "
        "pump_telemetry_by_hour_when_warning.recommended_flow_rate"
    )


def test_mapping_dependency_rejects_unknown_feature() -> None:
    configuration = _configuration()
    operator = configuration["profiles"]["pump_telemetry"]["assembly"]["pressure_flow_efficiency"]
    operator["interface"]["inputs"].append("$features.missing_feature")
    model = spec.Spec.model_validate(configuration)

    with pytest.raises(ValueError) as error:
        validation.validate_spec(model)

    assert str(error.value) == (
        "Operator pressure_flow_efficiency references unknown input feature: missing_feature"
    )


def test_new_document_validation_observes_an_edit() -> None:
    document = spec.Spec.model_validate(_configuration())
    validation.validate_spec(document)
    operator = document.profiles["pump_telemetry"].assembly["pressure_flow_efficiency"]
    operator.interface.inputs.append("$features.health_signal_normalized")
    document = spec.Spec.model_validate(document.model_dump())

    with pytest.raises(ValueError, match="cannot read feature .* from another profile"):
        validation.validate_spec(document)


def test_document_validation_rejects_blank_calculation_function_id() -> None:
    configuration = _configuration()
    configuration["functions"][" "] = configuration["functions"].pop("ratio")
    operator = configuration["profiles"]["pump_telemetry"]["assembly"]["pressure_flow_efficiency"]
    operator["compute"]["function"] = " "
    document = spec.Spec.model_validate(configuration)

    with pytest.raises(ValueError, match="Every function must define a non-empty string id"):
        validation.validate_spec(document)


def test_document_validation_rejects_blank_calculated_output() -> None:
    configuration = _configuration()
    dataset = configuration["profiles"]["pump_telemetry"]
    dataset["features"][" "] = dict(dataset["features"]["pressure_flow_efficiency"])
    dataset["assembly"]["pressure_flow_efficiency"]["interface"]["outputs"] = ["$features. "]
    document = spec.Spec.model_validate(configuration)

    with pytest.raises(ValueError, match="non-empty output feature names"):
        validation.validate_spec(document)


def test_topic_traversal_is_non_mutating_and_retains_invalid_declarations() -> None:
    document = spec.Spec.model_validate(_configuration())
    document.dimensions["machine_dimension"].resolutions[
        "machine_category"
    ].parent = "machine_category"
    dataset = document.profiles["pump"]
    dataset.assembly["bearing_temperature_by_pump"].interface.inputs = ["$features.missing"]
    other = document.profiles["pump_telemetry"]
    other.assembly["pressure_flow_efficiency"].compute.function = "missing"
    other.assembly["pump_mode"].compute.args = {"unexpected": spec.model.BindingArgument(None)}
    document.profiles["pump_copy"] = dataset.model_copy(update={"id": "pump_copy"}, deep=True)
    original = document.model_copy(deep=True)
    profiles = document.profile_items
    assembly = document.operators
    assert sum(item.id in {"pump", "pump_copy"} for _, item in profiles) == 2
    assert any(len(owners) > 1 for owners in document.feature_owners.values())
    assert any(item.compute.function not in document.functions for item in assembly)
    assert any(cycle for _, cycle in dimensions.iter_parent_cycles(document))
    assert any(item.order_dimensions for _, item in profiles)
    assert document.feature_producers
    assert any(source is None for source in document.input_sources.values())
    function_id, function, dataframe_inputs = next(document.functions.iter_functions())
    assert function_id == function.id
    assert dataframe_inputs == len(function.arguments_by_type.get("dataframe", {}))
    assert document.operator_dataframe_arguments
    assert document == original


def test_duplicate_feature_ownership_retains_all_candidates() -> None:
    document = spec.Spec.model_validate(_configuration())
    dataset = document.profiles["pump"]
    grain_keys = {
        document.dimensions[reference.dimension].resolutions[reference.resolution].key
        for profile in document.profiles.values()
        for reference in profile.grain
    }
    first, second = [feature for feature in dataset.features if feature not in grain_keys][:2]
    duplicate = dataset.model_copy(deep=True)
    duplicate.id = "another_dataset"
    duplicate.features = {
        second: dataset.features[second].model_copy(deep=True),
        first: dataset.features[first].model_copy(deep=True),
    }
    document.profiles[duplicate.id] = duplicate
    owners = document.feature_owners
    assert [document.profiles[key] for key in owners[first]] == [dataset, duplicate]
    assert [document.profiles[key] for key in owners[second]] == [dataset, duplicate]
    with pytest.raises(ValueError, match="Duplicate feature name"):
        feature_rules.validate_feature_ownership(document)
