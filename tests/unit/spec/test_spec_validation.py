import json
import pathlib

import pytest
from support import examples as example_support

from uptimely import spec
from uptimely.spec import model as spec_model
from uptimely.spec.python import assembly, conversion, feature, profile, ref
from uptimely.spec.validation import errors as validation_errors
from uptimely.spec.validation.rules.operators import contracts as operator_contracts

SPEC_PATH = example_support.EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json"
pytestmark = pytest.mark.usefixtures("example_projects")


def _write_configuration(tmp_path: pathlib.Path, configuration: dict, name: str) -> pathlib.Path:
    path = tmp_path / name
    path.write_text(json.dumps(configuration), encoding="utf-8")
    return path


def _escape_configuration() -> dict:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["functions"]["external_operator"] = {
        "returns": "any",
        "entrypoint": "examples.pump_analytics.functions.analytics:aggregate",
        "args": {},
    }
    target = configuration["profiles"]["pump_telemetry"]
    target["assembly"]["escape_first"] = {
        "compute": {
            "function": "external_operator",
            "args": {},
        },
        "interface": {
            "inputs": [
                "$features.bearing_temperature",
                "$features.health_signal_normalized",
                "$features.pump_id",
            ],
            "outputs": [],
        },
    }
    target["assembly"]["escape_second"] = {
        "compute": {
            "function": "external_operator",
            "args": {},
        },
        "interface": {
            "inputs": ["$features.bearing_temperature"],
            "outputs": [],
        },
    }
    return configuration


def test_mapping_locations_preserve_keys_duplicates_and_unresolved_functions() -> None:
    model = spec_model.Spec.model_validate(json.loads(SPEC_PATH.read_text(encoding="utf-8")))
    profile_id = next(iter(model.profiles))
    profile = model.profiles[profile_id]
    operator = next(iter(profile.assembly.values()))
    profile.assembly["alias"] = operator
    operator.compute.function = "missing"
    model.profiles["duplicate"] = profile.model_copy(update={"id": "duplicate"}, deep=True)

    locations = model.operator_items
    aliases = [(key, item) for key, item in locations if key[1] == "alias"]
    assert len(aliases) == 2
    assert aliases[0][1] is operator
    assert aliases[0][0] == (profile_id, "alias")
    assert model.operator_paths[aliases[0][0]][-1] == "alias"
    assert aliases[0][0][1] != operator.id
    same_profile_locations = [key for key, _ in locations if key[0] == profile_id]
    assert len(same_profile_locations) > 1
    assert all(model.operator_profiles[key] is profile for key in same_profile_locations)

    facts = same_profile_locations
    dimensions = frozenset(profile.dimension_ids)
    assert facts
    assert all(model.dimensions_by_profile[key[0]] == dimensions for key in facts)
    assert model.feature_owners


def test_traversal_retains_duplicate_declarations_and_feature_owners() -> None:
    model = spec_model.Spec.model_validate(json.loads(SPEC_PATH.read_text(encoding="utf-8")))
    pump_profile = model.profiles["pump"]
    model.profiles["pump_copy"] = pump_profile.model_copy(update={"id": "pump_copy"}, deep=True)

    locations = model.profile_items
    assert sum(item.id in {"pump", "pump_copy"} for _, item in locations) == 2
    feature_id = next(
        feature_id for feature_id in pump_profile.features if feature_id not in model.grain_key_ids
    )
    assert len(model.feature_owners[feature_id]) == 2


def test_location_indexes_describe_original_objects() -> None:
    model = spec_model.Spec.model_validate(json.loads(SPEC_PATH.read_text(encoding="utf-8")))
    profile_id = next(iter(model.profiles))
    profile = model.profiles[profile_id]
    profile.grain.append(spec_model.Grain(dimension="new_dimension", resolution="default"))
    model.dimensions["new_dimension"] = spec_model.Dimension(
        id="new_dimension",
        resolutions={"default": spec_model.Resolution(id="default", key="new_key", type="integer")},
    )
    item = next(iter(profile.assembly.values()))
    item.interface.inputs = ["$features.new_input"]
    item.interface.outputs = ["$features.new_output"]
    item.compute.args = {
        "nested": spec_model.BindingArgument(["$features.selected", "$dimensions.new_dimension"])
    }
    key, indexed = model.operator_items[0]
    assert indexed is item
    assert key[0] == profile_id
    assert "new_dimension" in profile.dimension_ids
    assert item.input_features == ["new_input"]
    assert item.output_features == ["new_output"]
    assert item.compute.references_by_prefix["$features."] == (("selected", ("nested", 0)),)
    assert item.compute.references_by_prefix["$dimensions."] == (("new_dimension", ("nested", 1)),)


def test_mapping_validation(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["functions"]["expand_telemetry"] = {
        "returns": "dataframe",
        "entrypoint": "examples.pump_analytics.functions.analytics:read_pump_telemetry",
        "args": {
            "source": {"type": "dataframe"},
        },
    }
    dataset = configuration["profiles"]["pump_telemetry"]
    dataset["features"]["expanded_feature"] = {"type": "float", "description": "Expanded feature"}
    dataset["assembly"]["expand_op"] = {
        "compute": {
            "function": "expand_telemetry",
            "args": {
                "source": "$profiles.pump.dataset",
            },
        },
        "interface": {
            "inputs": ["$features.bearing_temperature_max"],
            "outputs": ["$features.expanded_feature"],
        },
    }

    spec_path = tmp_path / "valid_mappings_spec.json"
    spec_path.write_text(json.dumps(configuration), encoding="utf-8")
    parsed_spec = spec.load_spec(spec_path)
    ds = parsed_spec.profiles["pump_telemetry"]

    assert "read_pump_telemetry" in ds.assembly
    assert "expand_op" in ds.assembly
    assert "expanded_feature" in ds.all_features

    bad_source_config = json.loads(json.dumps(configuration))
    bad_source_config["profiles"]["pump_telemetry"]["features"]["bad_source_feature"] = {
        "type": "float"
    }
    bad_source_config["profiles"]["pump_telemetry"]["assembly"]["bad_source"] = {
        "compute": {"function": "missing_read", "args": {}},
        "interface": {"inputs": [], "outputs": ["$features.bad_source_feature"]},
    }
    bad_source_path = tmp_path / "bad_source.json"
    bad_source_path.write_text(json.dumps(bad_source_config), encoding="utf-8")
    with pytest.raises(ValueError, match="operators reference unknown functions"):
        spec.load_spec(bad_source_path)

    bad_transform_config = json.loads(json.dumps(configuration))
    bad_transform_config["profiles"]["pump_telemetry"]["features"]["bad_transform_feature"] = {
        "type": "float"
    }
    bad_transform_config["profiles"]["pump_telemetry"]["assembly"]["bad_transform"] = {
        "compute": {"function": "missing_expand", "args": {}},
        "interface": {
            "inputs": ["$features.bearing_temperature_max"],
            "outputs": ["$features.bad_transform_feature"],
        },
    }
    bad_transform_path = tmp_path / "bad_transform.json"
    bad_transform_path.write_text(json.dumps(bad_transform_config), encoding="utf-8")
    with pytest.raises(ValueError, match="operators reference unknown functions"):
        spec.load_spec(bad_transform_path)


def test_unproduced_declared_features_warn_instead_of_failing(
    tmp_path: pathlib.Path,
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    dataset = configuration["profiles"]["pump_telemetry"]
    dataset["features"]["unproduced_feature"] = {"type": "float"}
    path = tmp_path / "unproduced_feature.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")

    with pytest.warns(
        UserWarning,
        match=(
            "profiles.pump_telemetry.features: Features have no producer operator: "
            "unproduced_feature"
        ),
    ):
        parsed_spec = spec.load_spec(path)

    assert "unproduced_feature" in parsed_spec.profiles["pump_telemetry"].features


def test_escape_mappings_preserve_logical_inputs_and_outputs(
    tmp_path: pathlib.Path,
) -> None:
    configuration = _escape_configuration()
    dataset_config = configuration["profiles"]["pump_telemetry"]
    dataset_config["features"]["external_result"] = {"type": "float"}
    dataset_config["features"]["external_followup"] = {"type": "float"}
    dataset_config["assembly"]["escape_first"]["interface"]["outputs"] = [
        "$features.external_result"
    ]
    dataset_config["assembly"]["escape_second"]["interface"]["inputs"] = []
    dataset_config["assembly"]["escape_second"]["interface"]["outputs"] = [
        "$features.external_followup"
    ]
    path = tmp_path / "escape.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")

    parsed_spec = spec.load_spec(path)
    assembly = parsed_spec.profiles["pump_telemetry"].assembly

    assert assembly["escape_first"].input_features == [
        "bearing_temperature",
        "health_signal_normalized",
        "pump_id",
    ]
    assert assembly["escape_first"].output_features == ["external_result"]
    assert assembly["escape_second"].input_features == []
    assert assembly["escape_second"].output_features == ["external_followup"]
    health_signal_producer = next(
        item for item in parsed_spec.operators if "health_signal_normalized" in item.output_features
    )
    assert parsed_spec.operator_kinds[("pump", health_signal_producer.id)] == "vectorize"


@pytest.mark.parametrize(
    ("field", "value", "message", "error_code", "path_suffix"),
    [
        (
            "inputs",
            ["$features.unknown_feature"],
            "Operator escape_first references unknown input feature: unknown_feature",
            None,
            None,
        ),
    ],
)
def test_escape_mappings_validate_declared_input_references(
    tmp_path: pathlib.Path,
    field: str,
    value: list[str],
    message: str,
    error_code: str | None,
    path_suffix: tuple[str, ...] | None,
) -> None:
    configuration = _escape_configuration()
    mapping_definition = configuration["profiles"]["pump_telemetry"]["assembly"]["escape_first"]
    mapping_definition["interface"][field] = value
    path = tmp_path / "invalid_escape.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")

    with pytest.raises(ValueError, match=message) as error:
        spec.load_spec(path)

    if error_code is not None:
        assert isinstance(error.value, validation_errors.SpecError)
        assert error.value.code == error_code
        assert error.value.path[-2:] == path_suffix


def test_python_conversion_and_json_loading_accept_output_only_escape_operator(
    tmp_path: pathlib.Path,
) -> None:
    declaration = profile.Profile(
        id="observations",
        assembly=[
            assembly.Operator(
                id="escape",
                interface=assembly.Interface(
                    outputs=[feature.Feature(id="external_result")],
                ),
                compute=assembly.Binding(
                    function=ref.function("example:escape", returns="any"),
                    arguments={},
                ),
            )
        ],
    )
    python_spec = spec.from_python(profiles=[declaration])
    python_operator = python_spec.profiles["observations"].assembly["escape"]
    assert python_operator.input_features == []
    assert python_operator.output_features == ["external_result"]

    path = tmp_path / "python_escape.json"
    path.write_text(json.dumps(conversion.to_dict(profiles=[declaration])), encoding="utf-8")
    json_spec = spec.load_spec(path)
    json_operator = json_spec.profiles["observations"].assembly["escape"]
    assert json_operator.input_features == []
    assert json_operator.output_features == ["external_result"]


def test_python_dataset_accepts_escape_feature_outputs() -> None:
    declaration = profile.Profile(
        id="observations",
        assembly=[
            assembly.Operator(
                id="escape",
                interface=assembly.Interface(
                    outputs=[feature.Feature(id="external_result")],
                ),
                compute=assembly.Binding(
                    function=ref.function("example:escape", returns="any"),
                    arguments={},
                ),
            )
        ],
    )

    assert declaration.to_model().assembly["escape"].output_features == ["external_result"]


def test_higher_dimensional_source_derives_collapse(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["functions"]["expand_telemetry"] = {
        "returns": "dataframe",
        "entrypoint": "examples.pump_analytics.functions.analytics:read_pump_telemetry",
        "args": {
            "source": {"type": "dataframe"},
        },
    }
    target = configuration["profiles"]["pump"]
    target["features"]["expanded_feature"] = {"type": "float"}
    target["assembly"]["expand_op"] = {
        "compute": {
            "function": "expand_telemetry",
            "args": {
                "source": "$profiles.pump_telemetry.dataset",
            },
        },
        "interface": {
            "inputs": ["$features.bearing_temperature"],
            "outputs": ["$features.expanded_feature"],
        },
    }
    path = tmp_path / "invalid_expand_input.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")

    document = spec.load_spec(path)
    assert document.operator_kinds[("pump", "expand_op")] == "collapse"


def test_shared_callable_can_derive_collapse(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["functions"]["conform_telemetry"] = {
        "returns": "dataframe",
        "entrypoint": "examples.pump_analytics.functions.analytics:read_pump_telemetry",
        "args": {
            "source": {"type": "dataframe"},
        },
    }
    target = configuration["profiles"]["pump"]
    target["features"]["conformed_feature"] = {"type": "float"}
    target["assembly"]["conform_op"] = {
        "compute": {
            "function": "conform_telemetry",
            "args": {
                "source": "$profiles.pump_telemetry.dataset",
            },
        },
        "interface": {
            "inputs": ["$features.bearing_temperature"],
            "outputs": ["$features.conformed_feature"],
        },
    }
    path = tmp_path / "invalid_conform_dimensions.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")

    document = spec.load_spec(path)
    assert document.operator_kinds[("pump", "conform_op")] == "collapse"


def _matching_key_configuration(key_selector: object, *, key_type: str = "array[string]") -> dict:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["functions"]["conform_with_keys"] = {
        "returns": "dataframe",
        "entrypoint": "examples.pump_analytics.functions.analytics:read_pump_telemetry",
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
        "entrypoint": "examples.pump_analytics.functions.analytics:read_pump_telemetry",
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


@pytest.mark.parametrize("operator_id", ["bearing_temperature_by_pump", "health_signal_normalized"])
def test_operator_rejects_explicit_source(tmp_path: pathlib.Path, operator_id: str) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["profiles"]["pump"]["assembly"][operator_id]["source"] = (
        "$profiles.pump_telemetry"
    )
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
            "must produce a non-dimension feature",
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
    with pytest.raises(ValueError, match="produced by multiple operators"):
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
def test_function_contract_validates_kind_inputs_and_return(
    tmp_path: pathlib.Path, field: str, value: object, message: str | None
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    if field == "returns":
        configuration["functions"]["aggregate"][field] = value
    else:
        configuration["functions"]["unmapped_vectorize"] = {
            "returns": "dataframe",
            "entrypoint": "examples.pump_analytics.functions.analytics:aggregate",
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
        "entrypoint": "examples.pump_analytics.functions.analytics:aggregate",
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
    with pytest.raises(ValueError, match="must reference a source feature"):
        spec.load_spec(path)
