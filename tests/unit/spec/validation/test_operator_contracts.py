import json
import pathlib

import pytest
from support import examples as example_support

from uptimely import spec
from uptimely.spec.validation import errors as validation_errors
from uptimely.spec.validation.rules.operators import contracts as operator_contracts

SPEC_PATH = example_support.EXAMPLES_ROOT / "artifacts/build/spec.json"


def _write_configuration(tmp_path: pathlib.Path, configuration: dict, name: str) -> pathlib.Path:
    path = tmp_path / name
    path.write_text(json.dumps(configuration), encoding="utf-8")
    return path


def _matching_key_configuration(key_selector: object, *, key_type: str = "array[string]") -> dict:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["functions"]["conform_with_keys"] = {
        "returns": "dataframe",
        "entrypoint": "example.src.io:read_pump_telemetry",
        "validate_signature": False,
        "args": {
            "source": {"type": "dataframe"},
            "on": {"type": key_type},
        },
    }
    target = configuration["profiles"]
    target["conformed_dataset"] = {
        "grain": target["pump"]["grain"],
        "features": {"conformed_value": {"type": "float"}},
        "assembly": {
            "conform_values": {
                "compute": {
                    "function": "conform_with_keys",
                    "args": {
                        "source": "$profiles.pump.dataset",
                        "on": key_selector,
                    },
                },
                "interface": {
                    "inputs": ["$features.bearing_temperature_max"],
                    "outputs": ["$features.conformed_value"],
                },
            }
        },
    }
    configuration["profiles"]["other_keys"] = {
        "name": "Other keys",
        "grain": [
            {"dimension": "machine_dimension", "resolution": "machine_category"},
            {"dimension": "machine_timestamp", "resolution": "timestamp"},
        ],
    }
    return configuration


@pytest.mark.parametrize(
    "key_selector",
    [
        "$profiles.@.grain.ids",
        "$profiles.pump.grain.ids",
    ],
)
def test_matching_key_selectors_validate_on_target_and_source(
    tmp_path: pathlib.Path, key_selector: object
) -> None:
    configuration = _matching_key_configuration(key_selector)
    path = _write_configuration(tmp_path, configuration, "matching_keys.json")

    spec_definition = spec.load_spec(path)
    assert operator_contracts.validate_matching_keys(spec_definition) is None


def test_grain_key_selector_is_a_matching_key_declaration() -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    key, operator = next(
        (key, operator)
        for key, operator in spec_definition.operator_items
        if key[1] == "bearing_temperature_by_pump"
    )

    assert operator.compute.args["dimensions"].root == "$profiles.@.grain.ids"
    assert [grain_key for grain_key, _ in spec_definition.matching_profile_keys[key]] == ["pump_id"]
    assert operator_contracts.validate_matching_keys(spec_definition) is None


@pytest.mark.parametrize(
    ("key_selector", "expected_code", "expected_dimension", "expected_index"),
    [
        (
            "$profiles.other_keys.grain.ids",
            "invalid_mapping_matching_key",
            "machine_category_id",
            None,
        ),
        (["$dimensions.missing.id"], "unknown_dimension_reference", "missing", 0),
    ],
)
def test_matching_key_errors_point_to_the_declared_key(
    tmp_path: pathlib.Path,
    key_selector: object,
    expected_code: str,
    expected_dimension: str,
    expected_index: int | None,
) -> None:
    configuration = _matching_key_configuration(key_selector)
    path = _write_configuration(tmp_path, configuration, "invalid_matching_key.json")

    with pytest.raises(validation_errors.SpecError) as error:
        spec.load_spec(path)

    assert error.value.code == expected_code
    assert error.value.path == (
        "profiles",
        "conformed_dataset",
        "assembly",
        "conform_values",
        "compute",
        "args",
        "on",
    ) + (() if expected_index is None else (expected_index,))
    assert expected_dimension in str(error.value)


def test_ignored_result_still_enforces_compute_dataframe_arity(tmp_path: pathlib.Path) -> None:
    configuration = _matching_key_configuration("$profiles.pump.dataset", key_type="dataframe")
    function = configuration["functions"]["conform_with_keys"]
    function["returns"] = "any"
    configuration["profiles"]["conformed_dataset"]["assembly"]["conform_values"]["interface"][
        "outputs"
    ] = ["$features.conformed_value"]
    path = _write_configuration(tmp_path, configuration, "dimension_key_dataframe.json")

    with pytest.raises(ValueError, match="invalid dataframe arity: 2"):
        spec.load_spec(path)


def test_conform_rejects_the_target_dataframe_as_an_argument(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["functions"]["conform_telemetry"] = {
        "returns": "dataframe",
        "entrypoint": "example.src.io:read_pump_telemetry",
        "args": {"source": {"type": "dataframe"}},
    }
    target = configuration["profiles"]["pump"]
    target["features"]["conformed_feature"] = {"type": "float"}
    target["assembly"]["conform_op"] = {
        "compute": {
            "function": "conform_telemetry",
            "args": {"source": "$profiles.@.dataset"},
        },
        "interface": {
            "inputs": ["$features.bearing_temperature"],
            "outputs": ["$features.conformed_feature"],
        },
    }
    path = tmp_path / "conform_target_argument.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")

    with pytest.raises(ValueError, match="cannot read feature .* from another profile"):
        spec.load_spec(path)


@pytest.mark.parametrize("feature_id", ["bearing_temperature_max", "health_signal_normalized"])
def test_operator_rejects_explicit_source(tmp_path: pathlib.Path, feature_id: str) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    profile = configuration["profiles"]["pump"]
    operator_id = example_support.operator_id_for_output(profile["assembly"], feature_id)
    profile["assembly"][operator_id]["source"] = "$profiles.pump_telemetry"
    invalid_operation_path = tmp_path / "invalid_aggregation_operation.json"
    invalid_operation_path.write_text(json.dumps(configuration), encoding="utf-8")

    with pytest.raises(ValueError, match="source"):
        spec.load_spec(invalid_operation_path)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("group_by", ["$dimensions.pump"], "group_by"),
        ("operations", {}, "operations"),
        (
            "interface",
            {
                "inputs": ["$features.bearing_temperature"],
                "outputs": ["$features.pump_id"],
            },
            "interface outputs must contain only features; pump_id",
        ),
        ("features", ["bearing_temperature_max"], "features"),
    ],
)
def test_collapse_validates_source_grouping_and_output_contract(
    tmp_path: pathlib.Path, field: str, value: object, message: str
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    collapse = configuration["profiles"]["pump"]["assembly"]["bearing_temperature_by_pump"]
    collapse[field] = value
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        spec.load_spec(path)


@pytest.mark.parametrize(
    ("inputs", "message"),
    [
        ([], "must reference a source feature"),
        (["$features.local_source"], "target profile"),
        (["$features.missing"], "unknown input feature"),
        (["$profiles.pump_telemetry"], "Operator interface must use"),
    ],
)
def test_collapse_validates_explicit_inputs(
    tmp_path: pathlib.Path, inputs: list, message: str
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["profiles"]["pump"]["features"]["local_source"] = {}
    collapse = configuration["profiles"]["pump"]["assembly"]["bearing_temperature_by_pump"]
    collapse["interface"]["inputs"] = inputs
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        spec.load_spec(path)


def test_collapse_inferred_dimensions_must_exist_in_source(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["profiles"]["pump_telemetry"]["grain"] = [
        item
        for item in configuration["profiles"]["pump_telemetry"]["grain"]
        if item["dimension"] != "machine_dimension"
    ]
    path = tmp_path / "invalid_dimensions.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    with pytest.raises(ValueError, match="Matching key pump_id is not in the grain"):
        spec.load_spec(path)


def test_collapse_catalog_requires_function_entrypoint(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["functions"]["aggregate"].pop("entrypoint")
    path = tmp_path / "missing_entrypoint.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    with pytest.raises(ValueError, match="entrypoint"):
        spec.load_spec(path)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("returns", "none", "compute binding must return a dataframe when merging"),
        ("args", {}, None),
    ],
)
def test_function_contract_validates_dataframe_inputs_and_return(
    tmp_path: pathlib.Path, field: str, value: object, message: str | None
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    if field == "returns":
        configuration["functions"]["invalid_aggregate"] = {
            **configuration["functions"]["aggregate"],
            field: value,
        }
        configuration["profiles"]["pump"]["assembly"]["bearing_temperature_by_pump"]["compute"][
            "function"
        ] = "invalid_aggregate"
    else:
        configuration["functions"]["unmapped_vectorize"] = {
            "returns": "dataframe",
            "entrypoint": "example.src.analytics:aggregate",
            "args": value,
        }
    path = tmp_path / "invalid_function_contract.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    if message is None:
        assert spec.load_spec(path).functions["unmapped_vectorize"].args == {}
    else:
        with pytest.raises(ValueError, match=message):
            spec.load_spec(path)


def test_ignored_return_contract_is_independent_of_operator_usage(
    tmp_path: pathlib.Path,
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["functions"]["unmapped_vectorize"] = {
        "returns": "any",
        "entrypoint": "example.src.analytics:aggregate",
        "args": {"dataset": {"type": "dataframe"}},
    }
    path = tmp_path / "unmatched_function_contract.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")

    assert spec.load_spec(path).functions["unmapped_vectorize"].returns == "any"


def test_collapse_rejects_inputs_from_multiple_datasets(
    tmp_path: pathlib.Path,
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    references = ["$features.bearing_temperature", "$features.health_signal_normalized"]
    collapse = configuration["profiles"]["pump"]["assembly"]["bearing_temperature_by_pump"]
    collapse["interface"]["inputs"] = references
    path = tmp_path / "mixed_inputs.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    with pytest.raises(ValueError, match="inputs must belong to one"):
        spec.load_spec(path)


def test_collapse_dimensions_alone_do_not_identify_input_dataset(
    tmp_path: pathlib.Path,
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    collapse = configuration["profiles"]["pump"]["assembly"]["bearing_temperature_by_pump"]
    collapse["interface"]["inputs"] = ["$features.pump_id"]
    path = tmp_path / "dimension_input.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    with pytest.raises(ValueError, match="interface inputs must contain only features; pump_id"):
        spec.load_spec(path)
