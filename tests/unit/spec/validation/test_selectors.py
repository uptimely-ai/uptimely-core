import json
import pathlib

import pytest
from support import examples as example_support

from uptimely import spec
from uptimely.spec import model, validation
from uptimely.spec.feature_graph import models

SPEC_PATH = example_support.EXAMPLES_ROOT / "artifacts/build/spec.json"


def test_dataset_dimension_selectors_resolve_for_host_and_foreign_datasets() -> None:
    args = {
        "host_keys": "$profiles.@.grain.ids",
        "source_keys": "$profiles.source.grain.ids",
        "source": "$profiles.source.dataset",
    }
    grain_keys = {"telemetry": ["pump", "timestamp"], "source": ["pump"]}

    binding = model.Binding(function="read", args=args)
    assert [identifier for identifier, _ in binding.references_by_prefix["$profiles."]] == [
        "@",
        "source",
        "source",
    ]
    assert binding.resolve_args("telemetry", identifiers_by_profile=grain_keys) == {
        "host_keys": ["pump", "timestamp"],
        "source_keys": ["pump"],
        "source": "source",
    }
    assert binding.profile_dependencies("telemetry") == ["source"]
    assert binding.profile_dataframe_references == ("source",)
    assert binding.profile_dataframe_references is binding.profile_dataframe_references
    assert binding.profile_dependencies("telemetry") == ["source"]


def test_system_and_subset_support_multiple_variables() -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    assert (
        sum(
            operator.produces_target_features(spec_definition, key)
            for key, operator in spec_definition.operator_items
        )
        == 13
    )
    collapse = spec_definition.profiles["pump"].assembly["bearing_temperature_by_pump"]
    assert collapse.compute.function == "aggregate"
    assert collapse.compute.args["aggregations"].root == {"bearing_temperature": "max"}
    system = spec.FeatureGraph(spec_definition)

    assert system.feature_names == {
        "bearing_temperature_max",
        "bearing_temperature_series_max",
        "bearing_temperature_category_max",
        "bearing_temperature_minute_max",
        "bearing_temperature_hour_max",
        "bearing_temperature_day_max",
        "health_signal_normalized",
        "max_capacity",
        "recommended_flow_rate",
        "recommended_differential_pressure",
        "energy_cost_score",
        "converged",
        "pressure_flow_efficiency",
        "bearing_temperature_delta",
        "bearing_temperature_rise",
        "vibration_delta",
        "pump_health_score",
        "pump_mode",
        "warning_hour_mean_differential_pressure",
        "warning_hour_mean_flow_rate",
        "warning_hour_mean_motor_power",
        "warning_hour_max_bearing_temperature",
        "warning_hour_max_vibration_rms",
        "operating_point_recommendation",
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
    profile = configuration["profiles"]["pump_telemetry"]
    operator_id = example_support.operator_id_for_output(
        profile["assembly"], "pressure_flow_efficiency"
    )
    operator = profile["assembly"][operator_id]
    operator["interface"]["outputs"] = []
    document = spec.Spec.model_validate(configuration)

    with pytest.raises(
        ValueError, match=f"Operator {operator_id} must declare one or more features"
    ):
        validation.validate_spec(document)


def test_spec_validation_rejects_duplicate_feature_names(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    profile = configuration["profiles"]["pump_telemetry"]
    operator_id = example_support.operator_id_for_output(
        profile["assembly"], "pressure_flow_efficiency"
    )
    duplicate = profile["assembly"][operator_id]
    configuration["profiles"]["duplicate_dataset"] = {
        "name": "Duplicate profile",
        "grain": profile["grain"],
        "features": {"pressure_flow_efficiency": profile["features"]["pressure_flow_efficiency"]},
        "assembly": {"pressure_flow_efficiency": duplicate},
    }
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(configuration), encoding="utf-8")

    with pytest.raises(ValueError, match="Duplicate feature name: pressure_flow_efficiency"):
        spec.load_spec(spec_path)


def test_spec_validation_rejects_duplicate_fragment_input_names(
    tmp_path: pathlib.Path,
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    profile = configuration["profiles"]["pump_telemetry"]
    profile["assembly"]["duplicate_input"] = {
        "compute": profile["assembly"]["read_pump_telemetry"]["compute"],
        "merge": configuration["profiles"]["pump"]["assembly"]["bearing_temperature_by_pump"][
            "merge"
        ],
        "interface": {"inputs": [], "outputs": ["$features.bearing_temperature"]},
    }
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(configuration), encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="Feature bearing_temperature is produced by multiple operators",
    ):
        spec.load_spec(spec_path)


def test_dimension_outputs_are_implicit_in_mapping(
    tmp_path: pathlib.Path,
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    outputs = configuration["profiles"]["pump_telemetry"]["assembly"]["read_pump_telemetry"][
        "interface"
    ]["outputs"]
    assert "$features.pump_id" not in outputs
    assert "$features.timestamp" not in outputs
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(configuration), encoding="utf-8")

    spec.load_spec(spec_path)


def test_spec_validation_rejects_unknown_vectorize_template(
    tmp_path: pathlib.Path,
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    profile = configuration["profiles"]["pump_telemetry_by_hour_when_warning"]
    operator_id = example_support.operator_id_for_output(
        profile["assembly"], "recommended_flow_rate"
    )
    profile["assembly"][operator_id]["compute"]["function"] = "missing_vectorize_template"
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(configuration), encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="operators reference unknown functions: missing_vectorize_template",
    ):
        spec.load_spec(spec_path)


def test_spec_validation_rejects_feature_dimension_name_collision(
    tmp_path: pathlib.Path,
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    profile = configuration["profiles"]["pump_telemetry"]
    operator_id = example_support.operator_id_for_output(profile["assembly"], "pump_mode")
    collision = json.loads(json.dumps(profile["assembly"][operator_id]))
    profile["assembly"]["pump_collision"] = {
        **collision,
        "interface": {"inputs": [], "outputs": ["$features.pump_id"]},
    }
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(configuration), encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="interface outputs must contain only features; pump_id",
    ):
        spec.load_spec(spec_path)


def test_spec_validation_rejects_cross_profile_feature_dependency(
    tmp_path: pathlib.Path,
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    pump_profile = configuration["profiles"]["pump"]
    operator_id = example_support.operator_id_for_output(
        pump_profile["assembly"], "health_signal_normalized"
    )
    calculation = json.loads(json.dumps(pump_profile["assembly"][operator_id]))
    calculation["interface"]["outputs"] = ["$features.health_signal_normalized_copy"]
    copied_feature = configuration["profiles"]["pump"]["features"]["health_signal_normalized"]
    configuration["profiles"]["pump_copy_profile"] = {
        "name": "Pump copy",
        "grain": configuration["profiles"]["pump"]["grain"],
        "features": {"health_signal_normalized_copy": copied_feature},
        "assembly": {"health_signal_normalized_copy": calculation},
    }
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(configuration), encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="cannot read feature .* from another profile",
    ):
        spec.load_spec(spec_path)
