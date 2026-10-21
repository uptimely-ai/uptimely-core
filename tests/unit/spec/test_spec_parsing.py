import json
import pathlib

import pydantic
import pytest
from conftest import EXAMPLES_ROOT

from uptimely import spec
from uptimely.spec import references, validation
from uptimely.spec.feature_graph import models

SPEC_PATH = EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json"


def _write_configuration(tmp_path: pathlib.Path, configuration: dict, name: str) -> pathlib.Path:
    path = tmp_path / name
    path.write_text(json.dumps(configuration), encoding="utf-8")
    return path


def test_spec_rejects_unknown_fields(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["unexpected"] = True

    with pytest.raises(pydantic.ValidationError, match="unexpected"):
        spec.load_spec(_write_configuration(tmp_path, configuration, "unknown.json"))


def test_spec_rejects_legacy_version_field(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["version"] = configuration.pop("spec_version")

    with pytest.raises(pydantic.ValidationError, match="version"):
        spec.load_spec(_write_configuration(tmp_path, configuration, "legacy-version.json"))


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


def test_spec_rejects_unsupported_version(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["spec_version"] = "9.9.9"

    with pytest.raises(pydantic.ValidationError, match="spec_version"):
        spec.load_spec(_write_configuration(tmp_path, configuration, "version.json"))


def test_spec_rejects_dimension_parent_cycles(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["dimensions"]["plant"]["parent"] = "pump"

    with pytest.raises(validation.SpecError) as error:
        spec.load_spec(_write_configuration(tmp_path, configuration, "cycle.json"))

    assert str(error.value) == (
        "dimensions.plant.parent: Dimension parent cycle: plant -> pump -> production_line -> plant"
    )
    assert error.value.code == "dimension_parent_cycle"
    assert error.value.path == ("dimensions", "plant", "parent")


def test_spec_rejects_duplicate_dataset_ids(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    duplicate = dict(configuration["entities"]["pump"]["datasets"][0])
    configuration["entities"]["pump"]["datasets"].append(duplicate)

    with pytest.raises(ValueError, match="Duplicate dataset id.*pump_dataset"):
        spec.load_spec(_write_configuration(tmp_path, configuration, "datasets.json"))


def test_spec_errors_expose_stable_code_and_path(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    duplicate = dict(configuration["entities"]["pump"]["datasets"][0])
    configuration["entities"]["pump_telemetry"]["datasets"].append(duplicate)

    with pytest.raises(validation.SpecError) as error:
        spec.load_spec(_write_configuration(tmp_path, configuration, "datasets.json"))

    assert error.value.code == "duplicate_dataset_id"
    assert error.value.path == ("entities", "pump", "datasets", "pump_dataset")
    assert str(error.value) == (
        "entities.pump.datasets.pump_dataset: Duplicate dataset id pump_dataset; "
        "already declared by entity pump_telemetry"
    )


def test_validation_reports_duplicate_dataset_before_invalid_dimension_parent(
    tmp_path: pathlib.Path,
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    duplicate = dict(configuration["entities"]["pump"]["datasets"][0])
    configuration["entities"]["pump_telemetry"]["datasets"].append(duplicate)
    configuration["dimensions"]["plant"]["parent"] = "missing_dimension"

    with pytest.raises(validation.SpecError) as error:
        spec.load_spec(_write_configuration(tmp_path, configuration, "multiple_errors.json"))

    assert error.value.code == "duplicate_dataset_id"
    assert error.value.path == ("entities", "pump", "datasets", "pump_dataset")
    assert str(error.value) == (
        "entities.pump.datasets.pump_dataset: Duplicate dataset id pump_dataset; "
        "already declared by entity pump_telemetry"
    )


def test_spec_rejects_unknown_write_function(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    dataset = configuration["entities"]["pump_telemetry"]["datasets"][0]
    dataset["mappings"]["write_pump_telemetry"]["binding"]["function"] = "missing_write"

    with pytest.raises(ValueError, match="mappings reference unknown functions: missing_write"):
        spec.load_spec(_write_configuration(tmp_path, configuration, "write.json"))


def test_spec_rejects_undeclared_binding_arguments(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    binding_args = configuration["entities"]["pump_telemetry"]["datasets"][0]["mappings"][
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

    assert references.resolve_binding_args(args, "telemetry") == {
        "feature": "bearing_temperature",
        "literal": "bearing_temperature_max",
        "nested": {"columns": ["flow_rate", "bearing_temperature"]},
    }


def test_feature_placeholder_resolves_to_bound_feature_id() -> None:
    args = {"output": "$features.@"}

    assert references.resolve_binding_args(args, "dataset", "calculated_feature") == {
        "output": "calculated_feature"
    }


def test_structural_references_compile_to_identifiers() -> None:
    args = {
        "current": "$datasets.@",
        "specific": "$datasets.pump_units",
        "dimension": "$dimensions.pump",
    }

    assert references.resolve_binding_args(args, "pump_telemetry_dataset") == {
        "current": "pump_telemetry_dataset",
        "specific": "pump_units",
        "dimension": "pump",
    }


def test_nested_selectors_resolve_without_changing_literal_values() -> None:
    args = {
        "nested": [
            "$datasets.@.dataframe",
            {"dataset": "$datasets.other.id", "feature": "$features.@.id"},
            "$dimensions.pump.id",
            "ordinary.id",
            0,
            None,
        ]
    }

    assert references.resolve_binding_args(args, "telemetry", "calculated") == {
        "nested": [
            "telemetry",
            {"dataset": "other", "feature": "calculated"},
            "pump",
            "ordinary.id",
            0,
            None,
        ]
    }
    assert references.dataset_dependencies(args, "telemetry") == ["telemetry"]
    assert references.resolve_binding_args({"feature": "$features.@.id"}, "telemetry") == {
        "feature": "$features.@.id"
    }


def test_system_and_subset_support_multiple_variables() -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    assert len(spec_definition.functions.by_operation("vectorize")) == 7
    collapse = spec_definition.entities["pump"].datasets[0].mappings["bearing_temperature_by_pump"]
    assert not hasattr(collapse, "source")
    assert collapse.binding.function == "maximum"
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
        "vibration_delta",
        "pump_health_score",
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
    mapping = configuration["entities"]["pump_telemetry"]["datasets"][0]["mappings"][
        "pressure_flow_efficiency"
    ]
    mapping["features"]["outputs"] = []
    document = spec.Spec.model_validate(configuration)

    with pytest.raises(
        ValueError, match="Mapping pressure_flow_efficiency must declare one or more features"
    ):
        validation.validate_spec(document)


def test_spec_validation_rejects_duplicate_feature_names(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    dataset = configuration["entities"]["pump_telemetry"]["datasets"][0]
    duplicate = dataset["mappings"]["pressure_flow_efficiency"]
    configuration["entities"]["duplicate"] = {
        "name": "Duplicate feature owner",
        "dimensions": ["pump"],
        "datasets": [
            {
                "id": "duplicate_dataset",
                "row_scope": {"grain": "", "filtering": "", "coverage": ""},
                "features": {
                    "pressure_flow_efficiency": dataset["features"]["pressure_flow_efficiency"]
                },
                "mappings": {"pressure_flow_efficiency": duplicate},
            }
        ],
    }
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(configuration), encoding="utf-8")

    with pytest.raises(ValueError, match="Duplicate feature name: pressure_flow_efficiency"):
        spec.load_spec(spec_path)


def test_spec_validation_rejects_duplicate_fragment_input_names(
    tmp_path: pathlib.Path,
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["entities"]["pump_telemetry"]["datasets"][0]["mappings"]["duplicate_input"] = {
        "binding": {"function": "read_pump_telemetry", "args": {}},
        "features": {"inputs": [], "outputs": ["$features.bearing_temperature"]},
    }
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(configuration), encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="Feature bearing_temperature is produced by multiple mappings",
    ):
        spec.load_spec(spec_path)


def test_dimension_outputs_are_implicit_in_mapping(
    tmp_path: pathlib.Path,
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["entities"]["pump_telemetry"]["datasets"][0]["mappings"]["read_pump_telemetry"][
        "features"
    ]["outputs"].remove("$features.plant")
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(configuration), encoding="utf-8")

    spec.load_spec(spec_path)


def test_spec_validation_rejects_unknown_vectorize_template(
    tmp_path: pathlib.Path,
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["entities"]["pump_telemetry"]["datasets"][0]["mappings"]["recommended_flow_rate"][
        "binding"
    ]["function"] = "missing_vectorize_template"
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(configuration), encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="mappings reference unknown functions: missing_vectorize_template",
    ):
        spec.load_spec(spec_path)


def test_spec_validation_rejects_feature_dimension_name_collision(
    tmp_path: pathlib.Path,
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    dataset = configuration["entities"]["pump_telemetry"]["datasets"][0]
    collision = json.loads(json.dumps(dataset["mappings"]["converged"]))
    dataset["mappings"]["pump_collision"] = {
        **collision,
        "features": {"inputs": [], "outputs": ["$features.pump"]},
    }
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(configuration), encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="Calculated feature names cannot duplicate entity dimensions: pump",
    ):
        spec.load_spec(spec_path)


def test_spec_validation_rejects_cross_dataset_feature_dependency(
    tmp_path: pathlib.Path,
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    calculation = configuration["entities"]["pump"]["datasets"][0]["mappings"].pop(
        "health_signal_normalized"
    )
    calculation["features"]["outputs"] = ["$features.health_signal_normalized_copy"]
    copied_feature = configuration["entities"]["pump"]["datasets"][0]["features"].pop(
        "health_signal_normalized"
    )
    configuration["entities"]["pump_copy"] = {
        "name": "Pump copy",
        "dimensions": ["pump"],
        "datasets": [
            {
                "id": "pump_copy_dataset",
                "row_scope": {"grain": "", "filtering": "", "coverage": ""},
                "features": {"health_signal_normalized_copy": copied_feature},
                "mappings": {"health_signal_normalized_copy": calculation},
            }
        ],
    }
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(configuration), encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="use a source resource operation",
    ):
        spec.load_spec(spec_path)
