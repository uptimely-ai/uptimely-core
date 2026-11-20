import json
import pathlib

import pytest
from support import examples as example_support

from uptimely import spec
from uptimely.spec import model as spec_model
from uptimely.spec.python import assembly, conversion, feature, profile, ref
from uptimely.spec.validation import errors as validation_errors

SPEC_PATH = example_support.EXAMPLES_ROOT / "artifacts/build/spec.json"


def _escape_configuration() -> dict:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["functions"]["external_operator"] = {
        "returns": "any",
        "entrypoint": "example.src.analytics:aggregate",
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
        feature_id for feature_id in pump_profile.features if feature_id not in model.identifier_ids
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
        "entrypoint": "example.src.io:read_pump_telemetry",
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
        "merge": configuration["profiles"]["pump"]["assembly"]["bearing_temperature_by_pump"][
            "merge"
        ],
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
    dataset_config["assembly"]["escape_first"]["interface"]["inputs"].remove("$features.pump_id")
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
    ]
    assert assembly["escape_first"].output_features == ["external_result"]
    assert assembly["escape_second"].input_features == []
    assert assembly["escape_second"].output_features == ["external_followup"]
    health_signal_producer = next(
        item for item in parsed_spec.operators if "health_signal_normalized" in item.output_features
    )
    key = ("pump", health_signal_producer.id)
    assert parsed_spec.operators_by_key[key].produces_target_features(parsed_spec, key)


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
                outputs=[feature.Feature(id="external_result")],
                compute=assembly.Bind(
                    ref.function("example:escape", returns="any"),
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
                outputs=[feature.Feature(id="external_result")],
                compute=assembly.Bind(
                    ref.function("example:escape", returns="any"),
                ),
            )
        ],
    )

    assert declaration.to_model().assembly["escape"].output_features == ["external_result"]


def test_higher_dimensional_source_derives_collapse(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["functions"]["expand_telemetry"] = {
        "returns": "dataframe",
        "entrypoint": "example.src.io:read_pump_telemetry",
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
        "merge": target["assembly"]["bearing_temperature_by_pump"]["merge"],
    }
    path = tmp_path / "invalid_expand_input.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")

    document = spec.load_spec(path)
    key = ("pump", "expand_op")
    assert (
        document.operators_by_key[key].grain_relationships(document, key)["pump_telemetry"]
        == "collapse"
    )


def test_shared_callable_can_derive_collapse(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["functions"]["conform_telemetry"] = {
        "returns": "dataframe",
        "entrypoint": "example.src.io:read_pump_telemetry",
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
        "merge": target["assembly"]["bearing_temperature_by_pump"]["merge"],
    }
    path = tmp_path / "invalid_conform_dimensions.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")

    document = spec.load_spec(path)
    key = ("pump", "conform_op")
    assert (
        document.operators_by_key[key].grain_relationships(document, key)["pump_telemetry"]
        == "collapse"
    )
