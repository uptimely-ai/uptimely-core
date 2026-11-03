import json
import logging
import pathlib

import pydantic
import pytest
from support import examples as example_support

from uptimely import spec
from uptimely.spec import model, validation
from uptimely.spec.feature_graph import models

SPEC_PATH = example_support.EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json"
pytestmark = pytest.mark.usefixtures("example_projects")


def test_loading_can_suppress_structure_debug_without_disabling_checks(
    tmp_path: pathlib.Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger="uptimely.spec")
    path = tmp_path / "spec.json"
    path.write_text("{}", encoding="utf-8")

    spec.load_spec(path, log_structure=False)

    assert not any("Document structure:" in message for message in caplog.messages)
    assert "  Semantic checks:" in caplog.messages
    caplog.clear()
    path.write_text('{"spec_version": true}', encoding="utf-8")
    with pytest.raises(ValueError, match="spec_version must be an integer"):
        spec.load_spec(path, log_structure=False)
    assert not caplog.records


def test_document_structure_checks_emit_debug_bullets(caplog: pytest.LogCaptureFixture) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    profiles = list(configuration["profiles"].values())
    action_count = sum(len(profile["actions"]) for profile in profiles)
    caplog.set_level(logging.DEBUG, logger="uptimely.spec.model")

    spec.Spec.model_validate(configuration)

    assert caplog.messages == [
        "\nSpec validation:\n  Document structure:",
        f"    - checking object keys as identifiers for {len(profiles)} profiles",
        "    - checking spec version is an integer",
        f"    - checking feature references for {action_count} actions",
    ]
    assert all(record.levelno == logging.DEBUG for record in caplog.records)


def test_loading_logs_one_spec_validation_heading(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="uptimely.spec")

    spec.load_spec(SPEC_PATH)

    assert caplog.messages.count("\nSpec validation:\n  Document structure:") == 1
    assert caplog.messages.count("  Semantic checks:") == 1
    assert sum(message.count("Spec validation:") for message in caplog.messages) == 1
    assert caplog.messages.index("  Semantic checks:") > caplog.messages.index(
        "\nSpec validation:\n  Document structure:"
    )


def test_invalid_action_reference_does_not_repeat_document_checks(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="uptimely.spec.model")

    with pytest.raises(pydantic.ValidationError, match=r"\$features"):
        model.ActionFeatures(inputs=["invalid"])

    assert not caplog.messages


@pytest.mark.parametrize("level", [logging.DEBUG, logging.INFO])
def test_structure_summary_counts_profiles_and_actions_once(
    caplog: pytest.LogCaptureFixture, level: int
) -> None:
    configuration = {
        "spec_version": 4,
        "profiles": {
            "profile_1": {
                "name": "First",
                "actions": {
                    f"action_{action}": {"binding": {"function": "read"}} for action in range(8)
                },
            },
            "profile_2": {
                "name": "Second",
                "actions": {
                    f"action_{action}": {"binding": {"function": "read"}} for action in range(5)
                },
            },
            "profile_3": {
                "name": "Third",
                "actions": {
                    f"action_{action}": {"binding": {"function": "read"}} for action in range(7)
                },
            },
        },
    }
    caplog.set_level(level, logger="uptimely.spec.model")

    spec.Spec.model_validate(configuration)

    assert caplog.messages == (
        [
            "\nSpec validation:\n  Document structure:",
            "    - checking object keys as identifiers for 3 profiles",
            "    - checking spec version is an integer",
            "    - checking feature references for 20 actions",
        ]
        if level == logging.DEBUG
        else []
    )


def test_structure_summary_counts_existing_resource_models(
    caplog: pytest.LogCaptureFixture,
) -> None:
    document = spec.Spec.model_validate_json(SPEC_PATH.read_text(encoding="utf-8"))
    profile_count = len(document.profile_items)
    action_count = len(document.actions)
    caplog.set_level(logging.DEBUG, logger="uptimely.spec.model")

    spec.Spec.model_validate({"profiles": document.profiles})

    assert caplog.messages == [
        "\nSpec validation:\n  Document structure:",
        f"    - checking object keys as identifiers for {profile_count} profiles",
        "    - checking spec version is an integer",
        f"    - checking feature references for {action_count} actions",
    ]


@pytest.mark.parametrize(
    "configuration",
    [
        {"profiles": ["invalid"]},
        {"profiles": {"profile": None}},
        {"profiles": {"profile": {"unknown": True}}},
        {"profiles": {"profile": {"actions": {"action": ["invalid"]}}}},
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
    assert len(caplog.messages) == 4


def _write_configuration(tmp_path: pathlib.Path, configuration: dict, name: str) -> pathlib.Path:
    path = tmp_path / name
    path.write_text(json.dumps(configuration), encoding="utf-8")
    return path


def test_spec_rejects_unknown_fields(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["unexpected"] = True

    with pytest.raises(pydantic.ValidationError, match="unexpected"):
        spec.load_spec(_write_configuration(tmp_path, configuration, "unknown.json"))


def test_spec_accepts_top_level_name(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["name"] = "Pump analytics"

    spec_definition = spec.load_spec(_write_configuration(tmp_path, configuration, "named.json"))

    assert spec_definition.name == "Pump analytics"


def test_loading_keeps_only_declarations_on_the_document() -> None:
    spec_definition = spec.load_spec(SPEC_PATH)

    validation.validate_spec(spec_definition)
    assert not hasattr(spec_definition, "calls")
    assert not hasattr(spec_definition, "path")


def test_canonical_model_rejects_file_loading_arguments() -> None:
    with pytest.raises(pydantic.ValidationError, match="json"):
        spec.Spec.model_validate({"json": str(SPEC_PATH)})


@pytest.mark.parametrize("version", [0, 1, 2, 3, "4", True])
def test_spec_rejects_unsupported_version(tmp_path: pathlib.Path, version: object) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["spec_version"] = version

    with pytest.raises(pydantic.ValidationError, match="spec_version"):
        spec.load_spec(_write_configuration(tmp_path, configuration, "version.json"))


def test_spec_rejects_dimension_parent_cycles(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["dimensions"]["machine"]["resolutions"]["plant"]["parent"] = "machine"

    with pytest.raises(validation.SpecError) as error:
        spec.load_spec(_write_configuration(tmp_path, configuration, "cycle.json"))

    assert str(error.value) == (
        "dimensions.machine.resolutions.machine.parent: Dimension resolution parent cycle: "
        "machine.machine -> machine.production_line -> machine.plant -> machine.machine"
    )
    assert error.value.code == "dimension_resolution_parent_cycle"
    assert error.value.path == ("dimensions", "machine", "resolutions", "machine", "parent")


def test_spec_errors_expose_stable_profile_identity_code_and_path() -> None:
    document = spec.Spec.model_validate_json(SPEC_PATH.read_text(encoding="utf-8"))
    document.profiles["wrong"] = model.Profile(id="different")

    with pytest.raises(validation.SpecError) as error:
        validation.validate_spec(document)

    assert error.value.code == "invalid_profile_id"
    assert error.value.path == ("profiles", "wrong")
    assert str(error.value) == (
        "profiles.wrong: Profile key wrong does not match profile id different"
    )


def test_spec_rejects_unknown_write_function(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    profile = configuration["profiles"]["pump_telemetry_dataset"]
    profile["actions"]["write_pump_telemetry"]["binding"]["function"] = "missing_write"

    with pytest.raises(ValueError, match="actions reference unknown functions: missing_write"):
        spec.load_spec(_write_configuration(tmp_path, configuration, "write.json"))


def test_spec_rejects_undeclared_binding_arguments(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    binding_args = configuration["profiles"]["pump_telemetry_dataset"]["actions"][
        "read_pump_telemetry"
    ]["binding"]["args"]
    binding_args["unexpected"] = "value"

    with pytest.raises(
        ValueError,
        match="Binding for function read_pump_telemetry has unknown arguments: unexpected",
    ):
        spec.load_spec(_write_configuration(tmp_path, configuration, "arguments.json"))


def test_feature_references_are_explicit_and_recursive() -> None:
    args = {
        "feature": "$features.bearing_temperature",
        "literal": "bearing_temperature_max",
        "nested": {"columns": ["$features.flow_rate", "$features.bearing_temperature"]},
    }

    binding = model.Binding(function="read", args=args)
    assert binding.resolve_args("telemetry") == {
        "feature": "bearing_temperature",
        "literal": "bearing_temperature_max",
        "nested": {"columns": ["flow_rate", "bearing_temperature"]},
    }


def test_feature_placeholder_resolves_to_bound_feature_id() -> None:
    args = {"output": "$features.@"}

    binding = model.Binding(function="calculate", args=args)
    assert binding.resolve_args("dataset", "calculated_feature") == {"output": "calculated_feature"}


def test_structural_references_compile_to_identifiers() -> None:
    args = {
        "current": "$profiles.@",
        "specific": "$profiles.pump_units",
        "dimension": "$dimensions.pump",
    }

    binding = model.Binding(function="read", args=args)
    assert binding.resolve_args("pump_telemetry_dataset") == {
        "current": "pump_telemetry_dataset",
        "specific": "pump_units",
        "dimension": "pump",
    }


def test_nested_selectors_resolve_without_changing_literal_values() -> None:
    args = {
        "nested": [
            "$profiles.@.dataframe",
            {"dataset": "$profiles.other.id", "feature": "$features.@.id"},
            "$dimensions.pump.id",
            "ordinary.id",
            0,
            None,
        ]
    }

    binding = model.Binding(function="calculate", args=args)
    assert binding.resolve_args("telemetry", "calculated") == {
        "nested": [
            "telemetry",
            {"dataset": "other", "feature": "calculated"},
            "pump",
            "ordinary.id",
            0,
            None,
        ]
    }
    assert binding.dataset_dependencies("telemetry") == ["telemetry"]
    assert model.Binding(function="read", args={"feature": "$features.@.id"}).resolve_args(
        "telemetry"
    ) == {"feature": "$features.@.id"}


def test_nested_model_binding_values_are_dumped_and_resolved() -> None:
    class NestedArgument(pydantic.BaseModel):
        feature: str

    binding = model.Binding(function="calculate")
    binding.args["nested"] = NestedArgument(feature="$features.flow_rate")

    assert binding.resolve_args("telemetry") == {"nested": {"feature": "flow_rate"}}


def test_resolve_args_defaults_to_empty_dictionary() -> None:
    assert model.Binding(function="read").resolve_args("telemetry") == {}


def test_dataset_dimension_selectors_resolve_for_host_and_foreign_datasets() -> None:
    args = {
        "host_keys": "$profiles.@.grain.ids",
        "source_keys": "$profiles.source.grain.ids",
        "source": "$profiles.source.dataframe",
    }
    grain_keys = {"telemetry": ["pump", "timestamp"], "source": ["pump"]}

    binding = model.Binding(function="read", args=args)
    assert [identifier for identifier, _ in binding.references_by_prefix["$profiles."]] == [
        "@",
        "source",
        "source",
    ]
    assert binding.resolve_args("telemetry", grain_keys_by_profile=grain_keys) == {
        "host_keys": ["pump", "timestamp"],
        "source_keys": ["pump"],
        "source": "source",
    }
    assert binding.dataset_dependencies("telemetry") == ["source"]
    assert binding.dataset_input_references == ("source",)
    assert binding.dataset_input_references is binding.dataset_input_references
    assert binding.dataset_dependencies("telemetry") == ["source"]


def test_system_and_subset_support_multiple_variables() -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    assert len(spec_definition.functions.by_kind("vectorize")) == 7
    collapse = spec_definition.profiles["pump_dataset"].actions["bearing_temperature_by_pump"]
    assert not hasattr(collapse, "source")
    assert collapse.binding.function == "aggregate"
    assert collapse.binding.args["feature"] == "$features.bearing_temperature"
    system = spec.FeatureGraph(spec_definition)

    assert system.feature_names == {
        "bearing_temperature_max",
        "health_signal_normalized",
        "recommended_flow_rate",
        "recommended_discharge_pressure",
        "energy_cost_score",
        "converged",
        "pressure_flow_efficiency",
        "bearing_temperature_delta",
        "bearing_temperature_rise",
        "vibration_delta",
        "pump_health_score",
        "operating_point_recommendation",
        "ratio",
    }
    assert system.graph is not None
    assert "bearing_temperature" in system.input_names
    assert any(
        isinstance(node.reference, models.FeatureNode)
        and node.reference.is_input
        and node.reference.name == "bearing_temperature"
        for node in system.graph
    )
    assert "machine" not in system.input_names

    subset = system.subset(["health_signal_normalized"])

    assert subset.output_names == ["health_signal_normalized"]
    assert "health_signal_normalized" in subset.feature_names
    assert "bearing_temperature_max" in subset.intermediate_names


def test_spec_validation_rejects_missing_output_variables() -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    action = configuration["profiles"]["pump_telemetry_dataset"]["actions"][
        "pressure_flow_efficiency"
    ]
    action["features"]["outputs"] = []
    document = spec.Spec.model_validate(configuration)

    with pytest.raises(
        ValueError, match="Action pressure_flow_efficiency must declare one or more features"
    ):
        validation.validate_spec(document)


def test_spec_validation_rejects_duplicate_feature_names(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    profile = configuration["profiles"]["pump_telemetry_dataset"]
    duplicate = profile["actions"]["pressure_flow_efficiency"]
    configuration["profiles"]["duplicate_dataset"] = {
        "name": "Duplicate profile",
        "grain": profile["grain"],
        "features": {"pressure_flow_efficiency": profile["features"]["pressure_flow_efficiency"]},
        "actions": {"pressure_flow_efficiency": duplicate},
    }
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(configuration), encoding="utf-8")

    with pytest.raises(ValueError, match="Duplicate feature name: pressure_flow_efficiency"):
        spec.load_spec(spec_path)


def test_spec_validation_rejects_duplicate_fragment_input_names(
    tmp_path: pathlib.Path,
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    profile = configuration["profiles"]["pump_telemetry_dataset"]
    profile["actions"]["duplicate_input"] = {
        "binding": profile["actions"]["read_pump_telemetry"]["binding"],
        "features": {"inputs": [], "outputs": ["$features.bearing_temperature"]},
    }
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(configuration), encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="Feature bearing_temperature is produced by multiple actions",
    ):
        spec.load_spec(spec_path)


def test_dimension_outputs_are_implicit_in_mapping(
    tmp_path: pathlib.Path,
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["profiles"]["pump_telemetry_dataset"]["actions"]["read_pump_telemetry"][
        "features"
    ]["outputs"].remove("$features.pump")
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(configuration), encoding="utf-8")

    spec.load_spec(spec_path)


def test_spec_validation_rejects_unknown_vectorize_template(
    tmp_path: pathlib.Path,
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["profiles"]["pump_telemetry_dataset"]["actions"]["recommended_flow_rate"][
        "binding"
    ]["function"] = "missing_vectorize_template"
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(configuration), encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="actions reference unknown functions: missing_vectorize_template",
    ):
        spec.load_spec(spec_path)


def test_spec_validation_rejects_feature_dimension_name_collision(
    tmp_path: pathlib.Path,
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    profile = configuration["profiles"]["pump_telemetry_dataset"]
    collision = json.loads(json.dumps(profile["actions"]["converged"]))
    profile["actions"]["pump_collision"] = {
        **collision,
        "features": {"inputs": [], "outputs": ["$features.pump"]},
    }
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(configuration), encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="Calculated feature names cannot duplicate profile grain keys: pump",
    ):
        spec.load_spec(spec_path)


def test_spec_validation_rejects_cross_dataset_feature_dependency(
    tmp_path: pathlib.Path,
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    calculation = json.loads(
        json.dumps(configuration["profiles"]["pump_dataset"]["actions"]["health_signal_normalized"])
    )
    calculation["features"]["outputs"] = ["$features.health_signal_normalized_copy"]
    copied_feature = configuration["profiles"]["pump_dataset"]["features"][
        "health_signal_normalized"
    ]
    configuration["profiles"]["pump_copy_dataset"] = {
        "name": "Pump copy",
        "grain": configuration["profiles"]["pump_dataset"]["grain"],
        "features": {"health_signal_normalized_copy": copied_feature},
        "actions": {"health_signal_normalized_copy": calculation},
    }
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(configuration), encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="cannot read feature .* from another dataset",
    ):
        spec.load_spec(spec_path)
