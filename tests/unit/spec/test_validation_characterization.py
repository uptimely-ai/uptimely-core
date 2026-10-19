import copy
import json
import pathlib

import pytest
from conftest import EXAMPLES_ROOT

from uptimely import spec
from uptimely.spec import validation
from uptimely.spec.validation import context as context_module
from uptimely.spec.validation import functions as function_validation
from uptimely.spec.validation import mapping_contracts as contracts_validation
from uptimely.spec.validation import mapping_inputs as inputs_validation

SPEC_PATH = EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json"


def _configuration() -> dict:
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


def test_document_validation_accepts_valid_document_without_mutation() -> None:
    document = spec.Spec.model_validate(_configuration())
    original = document.model_copy(deep=True)

    assert validation.validate_spec(document) is None
    assert document == original


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
def test_collapse_errors_precede_later_mapping_and_binding_faults(
    tmp_path: pathlib.Path, load_from_file: bool, inputs: list[str], message: str
) -> None:
    configuration = _configuration()
    mappings = configuration["entities"]["pump"]["datasets"][0]["mappings"]
    mappings["bearing_temperature_by_pump"]["features"]["inputs"] = inputs
    mappings["bearing_temperature_by_pump"]["binding"]["args"]["unexpected"] = None
    telemetry = configuration["entities"]["pump_telemetry"]["datasets"][0]["mappings"]
    telemetry["pressure_flow_efficiency"]["binding"]["args"]["unexpected"] = None

    with pytest.raises(ValueError) as error:
        if load_from_file:
            path = tmp_path / "invalid.json"
            path.write_text(json.dumps(configuration), encoding="utf-8")
            spec.load_spec(path)
        else:
            validation.validate_spec(spec.Spec.model_validate(configuration))

    assert type(error.value) is ValueError
    assert str(error.value) == message


def test_collapse_grouping_error_precedes_source_dimension_selector_error() -> None:
    configuration = _configuration()
    configuration["entities"]["pump_telemetry"]["dimensions"].remove("pump")
    mapping = configuration["entities"]["pump"]["datasets"][0]["mappings"][
        "bearing_temperature_by_pump"
    ]
    mapping["binding"]["args"]["unexpected"] = "$dimensions.missing"

    with pytest.raises(ValueError) as error:
        validation.validate_spec(spec.Spec.model_validate(configuration))

    assert str(error.value) == (
        "Collapse bearing_temperature_by_pump grouping dimensions must exist in source "
        "pump_telemetry_dataset"
    )


@pytest.mark.parametrize("invalid_binding", [False, True])
def test_binding_and_contract_paths_keep_their_existing_mapping_identifiers(
    invalid_binding: bool,
) -> None:
    document = spec.Spec.model_validate(_configuration())
    dataset = document.entities["pump_telemetry"].datasets[0]
    mapping = dataset.mappings.pop("pressure_flow_efficiency")
    dataset.mappings["alias"] = mapping
    if invalid_binding:
        mapping.binding.args["unexpected"] = None
        expected_id = "alias"
        expected_code = "invalid_binding_arguments"
    else:
        function = document.functions[mapping.binding.function]
        dataframe_arg = next(name for name, arg in function.args.items() if arg.type == "dataframe")
        mapping.binding.args[dataframe_arg] = "$datasets.pump_dataset.dataframe"
        expected_id = mapping.id
        expected_code = "invalid_mapping_dataset_input"

    with pytest.raises(validation.SpecError) as error:
        context = context_module.SpecValidationContext.build(document)
        if invalid_binding:
            function_validation.validate_bindings(context)
        else:
            sources = inputs_validation.validate_collapse(context)
            contracts_validation.validate_contracts(context, sources)

    assert error.value.code == expected_code
    assert error.value.path == (
        "entities",
        "pump_telemetry",
        "datasets",
        dataset.id,
        "mappings",
        expected_id,
        "binding",
        "args",
    )


def test_direct_semantic_validation_preserves_duplicate_dataset_error() -> None:
    model = spec.Spec.model_validate(_configuration())
    dataset = model.entities["pump"].datasets[0]
    model.entities["pump"].datasets.append(dataset.model_copy(deep=True))

    with pytest.raises(validation.SpecError) as error:
        validation.validate_spec(model)

    assert str(error.value) == (
        "entities.pump.datasets.pump_dataset: Duplicate dataset id pump_dataset; "
        "already declared by entity pump"
    )
    assert error.value.code == "duplicate_dataset_id"
    assert error.value.path == ("entities", "pump", "datasets", "pump_dataset")


def test_public_standalone_dataset_id_validation_rejects_duplicates() -> None:
    model = spec.Spec.model_validate(_configuration())
    dataset = model.entities["pump"].datasets[0]
    model.entities["pump"].datasets.append(dataset.model_copy(deep=True))

    with pytest.raises(validation.SpecError) as error:
        validation.validate_dataset_ids(model)

    assert error.value.code == "duplicate_dataset_id"
    assert error.value.path == ("entities", "pump", "datasets", "pump_dataset")


def test_document_validation_preserves_loading_phase_precedence() -> None:
    model = spec.Spec.model_validate(_configuration())
    dataset = model.entities["pump"].datasets[0]
    model.entities["pump"].datasets.append(dataset.model_copy(deep=True))
    model.dimensions["plant"].parent = "missing_dimension"

    with pytest.raises(validation.SpecError) as error:
        validation.validate_spec(model)

    assert str(error.value) == (
        "entities.pump.datasets.pump_dataset: Duplicate dataset id pump_dataset; "
        "already declared by entity pump"
    )
    assert error.value.code == "duplicate_dataset_id"
    assert error.value.path == ("entities", "pump", "datasets", "pump_dataset")


def test_document_validation_rejects_duplicate_output_producers() -> None:
    configuration = _configuration()
    mappings = configuration["entities"]["pump_telemetry"]["datasets"][0]["mappings"]
    mappings["duplicate"] = copy.deepcopy(mappings["pressure_flow_efficiency"])
    document = spec.Spec.model_validate(configuration)

    with pytest.raises(ValueError, match="produced by multiple mappings"):
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
    binding = configuration["entities"]["pump_telemetry"]["datasets"][0]["mappings"][
        "pressure_flow_efficiency"
    ]["binding"]
    binding["args"]["pressure_features"] = argument_value
    model = spec.Spec.model_validate(configuration)

    with pytest.raises(validation.SpecError) as error:
        validation.validate_spec(model)

    assert str(error.value) == (
        "entities.pump_telemetry.datasets.pump_telemetry_dataset.mappings."
        "pressure_flow_efficiency.binding.args: Reference $datasets.@.dataframe "
        "requires argument type dataframe, got string"
    )
    assert error.value.code == "invalid_binding_reference_type"
    assert error.value.path == (
        "entities",
        "pump_telemetry",
        "datasets",
        "pump_telemetry_dataset",
        "mappings",
        "pressure_flow_efficiency",
        "binding",
        "args",
    )


def test_binding_argument_name_contract_keeps_structured_error() -> None:
    configuration = _configuration()
    mapping = configuration["entities"]["pump_telemetry"]["datasets"][0]["mappings"][
        "pressure_flow_efficiency"
    ]
    mapping["binding"]["args"] = {"unexpected": None}
    model = spec.Spec.model_validate(configuration)

    with pytest.raises(validation.SpecError) as error:
        validation.validate_spec(model)

    assert error.value.code == "invalid_binding_arguments"
    assert error.value.path == (
        "entities",
        "pump_telemetry",
        "datasets",
        "pump_telemetry_dataset",
        "mappings",
        "pressure_flow_efficiency",
        "binding",
        "args",
    )
    assert "missing arguments:" in str(error.value)
    assert "unknown arguments: unexpected" in str(error.value)


def test_mapping_dependency_cycle_keeps_its_message() -> None:
    configuration = _configuration()
    mapping = configuration["entities"]["pump_telemetry"]["datasets"][0]["mappings"][
        "recommended_flow_rate"
    ]
    mapping["features"]["inputs"].append("$features.recommended_flow_rate")
    model = spec.Spec.model_validate(configuration)

    with pytest.raises(ValueError) as error:
        validation.validate_spec(model)

    assert str(error.value) == (
        "Mapping feature dependency cycle: pump_telemetry_dataset.recommended_flow_rate"
    )


def test_mapping_dependency_rejects_unknown_feature() -> None:
    configuration = _configuration()
    mapping = configuration["entities"]["pump_telemetry"]["datasets"][0]["mappings"][
        "pressure_flow_efficiency"
    ]
    mapping["features"]["inputs"].append("$features.missing_feature")
    model = spec.Spec.model_validate(configuration)

    with pytest.raises(ValueError) as error:
        validation.validate_spec(model)

    assert str(error.value) == (
        "Mapping pressure_flow_efficiency references unknown input feature: missing_feature"
    )


def test_document_validation_rebuilds_indexes_after_an_edit() -> None:
    document = spec.Spec.model_validate(_configuration())
    validation.validate_spec(document)
    mapping = document.entities["pump_telemetry"].datasets[0].mappings["pressure_flow_efficiency"]
    mapping.features.inputs.append("$features.health_signal_normalized")

    with pytest.raises(ValueError, match="cannot read feature .* from another dataset"):
        validation.validate_spec(document)


def test_document_validation_rejects_blank_calculation_function_id() -> None:
    configuration = _configuration()
    configuration["functions"][" "] = configuration["functions"].pop("pressure_flow_efficiency")
    mapping = configuration["entities"]["pump_telemetry"]["datasets"][0]["mappings"][
        "pressure_flow_efficiency"
    ]
    mapping["binding"]["function"] = " "
    document = spec.Spec.model_validate(configuration)

    with pytest.raises(ValueError, match="Every function must define a non-empty string id"):
        validation.validate_spec(document)


def test_document_validation_rejects_blank_calculated_output() -> None:
    configuration = _configuration()
    dataset = configuration["entities"]["pump_telemetry"]["datasets"][0]
    dataset["features"][" "] = dataset["features"].pop("pressure_flow_efficiency")
    dataset["mappings"]["pressure_flow_efficiency"]["features"]["outputs"] = ["$features. "]
    document = spec.Spec.model_validate(configuration)

    with pytest.raises(ValueError, match="Every calculation must define a non-empty output"):
        validation.validate_spec(document)
