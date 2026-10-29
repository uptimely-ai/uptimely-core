import copy
import json
import pathlib

import pytest
from support import examples as example_support

from uptimely import spec
from uptimely.spec import validation
from uptimely.spec.validation.rules import actions as action_rules
from uptimely.spec.validation.rules import (
    bindings,
    dimensions,
    functions,
)
from uptimely.spec.validation.rules import datasets as dataset_rules
from uptimely.spec.validation.rules import features as feature_rules
from uptimely.spec.validation.rules.actions import contracts as contracts_validation
from uptimely.spec.validation.rules.actions import dependencies
from uptimely.spec.validation.rules.actions import inputs as action_inputs
from uptimely.spec.validation.rules.actions import outputs as action_outputs

SPEC_PATH = example_support.EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json"
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
    action = (
        document.entities["pump_telemetry"]
        .datasets["pump_telemetry_dataset"]
        .actions["pressure_flow_efficiency"]
    )
    action.features.inputs = []
    action.binding.args["dependency_hint"] = "$features.bearing_temperature"

    facts = next(item for item in action_rules.iter_actions(document) if item.action is action)

    assert facts.inputs == ()
    assert "bearing_temperature" in facts.feature_selectors


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
            "Collapse bearing_temperature_by_pump cannot use its target dataset as source",
        ),
        (
            ["$features.bearing_temperature", "$features.health_signal_normalized"],
            "Collapse bearing_temperature_by_pump input features must belong to one dataset; "
            "use expand to combine inputs from different datasets",
        ),
    ],
)
def test_collapse_rules_report_their_own_fault_without_validating_bindings(
    tmp_path: pathlib.Path, load_from_file: bool, inputs: list[str], message: str
) -> None:
    configuration = _configuration()
    action = configuration["entities"]["pump"]["datasets"]["pump_dataset"]["actions"][
        "bearing_temperature_by_pump"
    ]
    action["features"]["inputs"] = inputs
    action["binding"]["args"]["unexpected"] = None
    if load_from_file:
        path = tmp_path / "invalid.json"
        path.write_text(json.dumps(configuration), encoding="utf-8")
        document = spec.Spec.model_validate_json(path.read_text(encoding="utf-8"))
    else:
        document = spec.Spec.model_validate(configuration)
    with pytest.raises(ValueError, match=message):
        action_inputs.validate_source_feature(document)
        action_inputs.validate_feature_owner(document)
        action_inputs.validate_source_count(document)
        action_inputs.validate_source_target(document)
    with pytest.raises(validation.SpecError, match="unknown arguments: unexpected"):
        bindings.validate_arguments(document)


def test_independent_rules_report_grouping_and_dimension_reference_faults() -> None:
    configuration = _configuration()
    configuration["entities"]["pump_telemetry"]["dimensions"].remove("pump")
    action = configuration["entities"]["pump"]["datasets"]["pump_dataset"]["actions"][
        "bearing_temperature_by_pump"
    ]
    action["binding"]["args"]["unexpected"] = "$dimensions.missing"
    document = spec.Spec.model_validate(configuration)
    with pytest.raises(ValueError, match="grouping dimensions must exist in source"):
        action_inputs.validate_grouping_dimensions(document)
    with pytest.raises(validation.SpecError, match="unknown dimension: missing"):
        action_inputs.validate_dimension_reference(document)


@pytest.mark.parametrize("invalid_binding", [False, True])
def test_binding_and_contract_paths_keep_their_existing_action_identifiers(
    invalid_binding: bool,
) -> None:
    document = spec.Spec.model_validate(_configuration())
    dataset = document.entities["pump_telemetry"].datasets["pump_telemetry_dataset"]
    action = dataset.actions.pop("pressure_flow_efficiency")
    dataset.actions["alias"] = action
    if invalid_binding:
        action.binding.args["unexpected"] = None
        expected_id = "alias"
        expected_code = "invalid_binding_arguments"
        validate = bindings.validate_arguments
    else:
        function = document.functions[action.binding.function]
        argument = next(name for name, arg in function.args.items() if arg.type == "dataframe")
        action.binding.args[argument] = "$datasets.pump_dataset.dataframe"
        expected_id = action.id
        expected_code = "invalid_mapping_dataset_input"
        validate = contracts_validation.validate_target_input
    with pytest.raises(validation.SpecError) as error:
        validate(document)
    assert error.value.code == expected_code
    assert error.value.path == (
        "entities",
        "pump_telemetry",
        "datasets",
        dataset.id,
        "actions",
        expected_id,
        "binding",
        "args",
    )


def test_direct_semantic_validation_preserves_duplicate_dataset_error() -> None:
    model = spec.Spec.model_validate(_configuration())
    dataset = model.entities["pump"].datasets["pump_dataset"]
    model.entities["pump_telemetry"].datasets[dataset.id] = dataset.model_copy(deep=True)

    with pytest.raises(validation.SpecError) as error:
        validation.validate_spec(model)

    assert str(error.value) == (
        "entities.pump.datasets.pump_dataset: Duplicate dataset id pump_dataset; "
        "already declared by entity pump_telemetry"
    )
    assert error.value.code == "duplicate_dataset_id"
    assert error.value.path == ("entities", "pump", "datasets", "pump_dataset")


def test_public_standalone_dataset_id_validation_rejects_duplicates() -> None:
    model = spec.Spec.model_validate(_configuration())
    dataset = model.entities["pump"].datasets["pump_dataset"]
    model.entities["pump_telemetry"].datasets[dataset.id] = dataset.model_copy(deep=True)

    with pytest.raises(validation.SpecError) as error:
        validation.validate_dataset_ids(model)

    assert error.value.code == "duplicate_dataset_id"
    assert error.value.path == ("entities", "pump", "datasets", "pump_dataset")


def test_duplicate_ids_block_action_cycle_validation() -> None:
    document = spec.Spec.model_validate(_configuration())
    dataset = document.entities["pump"].datasets["pump_dataset"]
    document.entities["pump_telemetry"].datasets[dataset.id] = dataset.model_copy(deep=True)
    action = dataset.actions["health_signal_normalized"]
    action.features.inputs.append("$features.health_signal_normalized")
    with pytest.raises(validation.SpecError) as error:
        validation.validate_spec(document)
    assert error.value.code == "duplicate_dataset_id"


def test_document_validation_rejects_duplicate_output_producers() -> None:
    configuration = _configuration()
    actions = configuration["entities"]["pump_telemetry"]["datasets"]["pump_telemetry_dataset"][
        "actions"
    ]
    actions["duplicate"] = copy.deepcopy(actions["pressure_flow_efficiency"])
    document = spec.Spec.model_validate(configuration)

    with pytest.raises(ValueError, match="produced by multiple actions"):
        validation.validate_spec(document)


@pytest.mark.parametrize(
    ("argument_type", "argument_value"),
    [
        ("array[string]", ["$features.discharge_pressure", "$datasets.@.dataframe"]),
        (
            "object{str: string}",
            {"nested": ["$features.discharge_pressure", "$datasets.@.dataframe"]},
        ),
    ],
)
def test_nested_binding_selectors_preserve_expected_argument_type(
    argument_type: str, argument_value: list[str] | dict[str, list[str]]
) -> None:
    configuration = _configuration()
    function = configuration["functions"]["pressure_flow_efficiency"]
    function["args"]["pressure_features"]["type"] = argument_type
    binding = configuration["entities"]["pump_telemetry"]["datasets"]["pump_telemetry_dataset"][
        "actions"
    ]["pressure_flow_efficiency"]["binding"]
    binding["args"]["pressure_features"] = argument_value
    model = spec.Spec.model_validate(configuration)

    with pytest.raises(validation.SpecError) as error:
        validation.validate_spec(model)

    assert str(error.value) == (
        "entities.pump_telemetry.datasets.pump_telemetry_dataset.actions."
        "pressure_flow_efficiency.binding.args: Reference $datasets.@.dataframe "
        "requires argument type dataframe, got string"
    )
    assert error.value.code == "invalid_binding_reference_type"
    assert error.value.path == (
        "entities",
        "pump_telemetry",
        "datasets",
        "pump_telemetry_dataset",
        "actions",
        "pressure_flow_efficiency",
        "binding",
        "args",
    )


def test_binding_argument_name_contract_keeps_structured_error() -> None:
    configuration = _configuration()
    action = configuration["entities"]["pump_telemetry"]["datasets"]["pump_telemetry_dataset"][
        "actions"
    ]["pressure_flow_efficiency"]
    action["binding"]["args"] = {"unexpected": None}
    model = spec.Spec.model_validate(configuration)

    with pytest.raises(validation.SpecError) as error:
        validation.validate_spec(model)

    assert error.value.code == "invalid_binding_arguments"
    assert error.value.path == (
        "entities",
        "pump_telemetry",
        "datasets",
        "pump_telemetry_dataset",
        "actions",
        "pressure_flow_efficiency",
        "binding",
        "args",
    )
    assert "missing arguments:" in str(error.value)
    assert "unknown arguments: unexpected" in str(error.value)


def test_mapping_dependency_cycle_keeps_its_message() -> None:
    configuration = _configuration()
    action = configuration["entities"]["pump_telemetry"]["datasets"]["pump_telemetry_dataset"][
        "actions"
    ]["recommended_flow_rate"]
    action["features"]["inputs"].append("$features.recommended_flow_rate")
    model = spec.Spec.model_validate(configuration)

    with pytest.raises(ValueError) as error:
        validation.validate_spec(model)

    assert str(error.value) == (
        "Action feature dependency cycle: pump_telemetry_dataset.recommended_flow_rate"
    )


def test_mapping_dependency_rejects_unknown_feature() -> None:
    configuration = _configuration()
    action = configuration["entities"]["pump_telemetry"]["datasets"]["pump_telemetry_dataset"][
        "actions"
    ]["pressure_flow_efficiency"]
    action["features"]["inputs"].append("$features.missing_feature")
    model = spec.Spec.model_validate(configuration)

    with pytest.raises(ValueError) as error:
        validation.validate_spec(model)

    assert str(error.value) == (
        "Action pressure_flow_efficiency references unknown input feature: missing_feature"
    )


def test_document_validation_rebuilds_indexes_after_an_edit() -> None:
    document = spec.Spec.model_validate(_configuration())
    validation.validate_spec(document)
    action = (
        document.entities["pump_telemetry"]
        .datasets["pump_telemetry_dataset"]
        .actions["pressure_flow_efficiency"]
    )
    action.features.inputs.append("$features.health_signal_normalized")

    with pytest.raises(ValueError, match="cannot read feature .* from another dataset"):
        validation.validate_spec(document)


def test_document_validation_rejects_blank_calculation_function_id() -> None:
    configuration = _configuration()
    configuration["functions"][" "] = configuration["functions"].pop("pressure_flow_efficiency")
    action = configuration["entities"]["pump_telemetry"]["datasets"]["pump_telemetry_dataset"][
        "actions"
    ]["pressure_flow_efficiency"]
    action["binding"]["function"] = " "
    document = spec.Spec.model_validate(configuration)

    with pytest.raises(ValueError, match="Every function must define a non-empty string id"):
        validation.validate_spec(document)


def test_document_validation_rejects_blank_calculated_output() -> None:
    configuration = _configuration()
    dataset = configuration["entities"]["pump_telemetry"]["datasets"]["pump_telemetry_dataset"]
    dataset["features"][" "] = dict(dataset["features"]["pressure_flow_efficiency"])
    dataset["actions"]["pressure_flow_efficiency"]["features"]["outputs"] = ["$features. "]
    document = spec.Spec.model_validate(configuration)

    with pytest.raises(ValueError, match="Every calculation must define a non-empty output"):
        validation.validate_spec(document)


def test_topic_traversal_is_non_mutating_and_retains_invalid_declarations() -> None:
    document = spec.Spec.model_validate(_configuration())
    document.dimensions["plant"].parent = "plant"
    dataset = document.entities["pump"].datasets["pump_dataset"]
    dataset.actions["bearing_temperature_by_pump"].features.inputs = ["$features.missing"]
    other = document.entities["pump_telemetry"].datasets["pump_telemetry_dataset"]
    other.actions["pressure_flow_efficiency"].binding.function = "missing"
    other.actions["recommended_flow_rate"].binding.args = {"unexpected": None}
    document.entities["pump_telemetry"].datasets[dataset.id] = dataset.model_copy(deep=True)
    original = document.model_copy(deep=True)
    datasets = tuple(dataset_rules.iter_datasets(document))
    actions = tuple(action_rules.iter_actions(document))
    assert sum(item.dataset.id == dataset.id for item in datasets) == 2
    assert any(len(owners) > 1 for owners in feature_rules.feature_owners(document).values())
    assert any(item.function is None for item in actions)
    assert any(cycle for _, cycle in dimensions.iter_parent_cycles(document))
    assert next(dataset_rules.iter_order_dimensions(document), None) is not None
    assert next(action_outputs.iter_output_datasets(document), None) is not None
    producers = dependencies.feature_producers(actions, frozenset(document.dimensions))
    assert producers
    assert any(item.source is None for item in action_inputs.iter_input_sources(document))
    assert dependencies.find_action_cycle(actions, producers) is None
    assert next(functions.iter_functions(document), None) is not None
    assert next(contracts_validation.iter_action_contracts(document), None) is not None
    assert document == original


def test_duplicate_feature_ownership_retains_all_candidates() -> None:
    document = spec.Spec.model_validate(_configuration())
    dataset = document.entities["pump"].datasets["pump_dataset"]
    first, second = [f for f in dataset.features if f not in document.dimensions][:2]
    duplicate = dataset.model_copy(deep=True)
    duplicate.id = "another_dataset"
    duplicate.features = {
        second: dataset.features[second].model_copy(deep=True),
        first: dataset.features[first].model_copy(deep=True),
    }
    document.entities["pump"].datasets[duplicate.id] = duplicate
    owners = feature_rules.feature_owners(document)
    assert [item.dataset for item in owners[first]] == [dataset, duplicate]
    assert [item.dataset for item in owners[second]] == [dataset, duplicate]
    with pytest.raises(ValueError, match="Duplicate feature name"):
        feature_rules.validate_feature_ownership(document)
