import json
import pathlib

import pydantic
import pytest
from support import examples as example_support

from uptimely import spec
from uptimely.spec import binding_resolution, references, validation
from uptimely.spec.feature_graph import models

SPEC_PATH = example_support.EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json"
pytestmark = pytest.mark.usefixtures("example_projects")


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


@pytest.mark.parametrize("version", [0, 1, 2, "3", True])
def test_spec_rejects_unsupported_version(tmp_path: pathlib.Path, version: object) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["spec_version"] = version

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


def test_spec_errors_expose_stable_code_and_path(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    duplicate = dict(configuration["entities"]["pump"]["datasets"]["pump_dataset"])
    configuration["entities"]["pump_telemetry"]["datasets"]["pump_dataset"] = duplicate

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
    duplicate = dict(configuration["entities"]["pump"]["datasets"]["pump_dataset"])
    configuration["entities"]["pump_telemetry"]["datasets"]["pump_dataset"] = duplicate
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
    dataset = configuration["entities"]["pump_telemetry"]["datasets"]["pump_telemetry_dataset"]
    dataset["actions"]["write_pump_telemetry"]["binding"]["function"] = "missing_write"

    with pytest.raises(ValueError, match="actions reference unknown functions: missing_write"):
        spec.load_spec(_write_configuration(tmp_path, configuration, "write.json"))


def test_spec_rejects_undeclared_binding_arguments(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    binding_args = configuration["entities"]["pump_telemetry"]["datasets"][
        "pump_telemetry_dataset"
    ]["actions"]["read_pump_telemetry"]["binding"]["args"]
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

    assert binding_resolution.resolve_binding_args(args, "telemetry") == {
        "feature": "bearing_temperature",
        "literal": "bearing_temperature_max",
        "nested": {"columns": ["flow_rate", "bearing_temperature"]},
    }


def test_feature_placeholder_resolves_to_bound_feature_id() -> None:
    args = {"output": "$features.@"}

    assert binding_resolution.resolve_binding_args(args, "dataset", "calculated_feature") == {
        "output": "calculated_feature"
    }


def test_structural_references_compile_to_identifiers() -> None:
    args = {
        "current": "$datasets.@",
        "specific": "$datasets.pump_units",
        "dimension": "$dimensions.pump",
    }

    assert binding_resolution.resolve_binding_args(args, "pump_telemetry_dataset") == {
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

    assert binding_resolution.resolve_binding_args(args, "telemetry", "calculated") == {
        "nested": [
            "telemetry",
            {"dataset": "other", "feature": "calculated"},
            "pump",
            "ordinary.id",
            0,
            None,
        ]
    }
    assert binding_resolution.dataset_dependencies(args, "telemetry") == ["telemetry"]
    assert binding_resolution.resolve_binding_args({"feature": "$features.@.id"}, "telemetry") == {
        "feature": "$features.@.id"
    }


def test_resolve_binding_args_defaults_none_to_empty_dictionary() -> None:
    assert binding_resolution.resolve_binding_args(None, "telemetry") == {}


@pytest.mark.parametrize("args", [[], "", 0, False, ()])
def test_resolve_binding_args_rejects_non_dictionary_arguments(args: object) -> None:
    with pytest.raises(TypeError, match="Binding arguments must be a dictionary or None"):
        binding_resolution.resolve_binding_args(args, "telemetry")  # type: ignore[arg-type]


def test_dataset_dimension_selectors_resolve_for_host_and_foreign_datasets() -> None:
    args = {
        "host_keys": "$datasets.@.dimensions.ids",
        "source_keys": "$datasets.source.dimensions.ids",
        "source": "$datasets.source.dataframe",
    }
    dimension_ids = {"telemetry": ["pump", "timestamp"], "source": ["pump"]}

    assert references.structural_references(args, "$datasets.") == [
        "@",
        "source",
        "source",
    ]
    assert binding_resolution.resolve_binding_args(
        args,
        "telemetry",
        dimension_ids_by_dataset=dimension_ids,
    ) == {
        "host_keys": ["pump", "timestamp"],
        "source_keys": ["pump"],
        "source": "source",
    }
    assert binding_resolution.dataset_dependencies(args, "telemetry") == ["source"]


def test_system_and_subset_support_multiple_variables() -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    assert len(spec_definition.functions.by_kind("vectorize")) == 7
    collapse = (
        spec_definition.entities["pump"]
        .datasets["pump_dataset"]
        .actions["bearing_temperature_by_pump"]
    )
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
    action = configuration["entities"]["pump_telemetry"]["datasets"]["pump_telemetry_dataset"][
        "actions"
    ]["pressure_flow_efficiency"]
    action["features"]["outputs"] = []
    document = spec.Spec.model_validate(configuration)

    with pytest.raises(
        ValueError, match="Action pressure_flow_efficiency must declare one or more features"
    ):
        validation.validate_spec(document)


def test_spec_validation_rejects_duplicate_feature_names(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    dataset = configuration["entities"]["pump_telemetry"]["datasets"]["pump_telemetry_dataset"]
    duplicate = dataset["actions"]["pressure_flow_efficiency"]
    configuration["entities"]["duplicate"] = {
        "name": "Duplicate feature owner",
        "dimensions": ["pump"],
        "datasets": {
            "duplicate_dataset": {
                "row_scope": {"grain": "", "filtering": "", "coverage": ""},
                "features": {
                    "pressure_flow_efficiency": dataset["features"]["pressure_flow_efficiency"]
                },
                "actions": {"pressure_flow_efficiency": duplicate},
            }
        },
    }
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(configuration), encoding="utf-8")

    with pytest.raises(ValueError, match="Duplicate feature name: pressure_flow_efficiency"):
        spec.load_spec(spec_path)


def test_spec_validation_rejects_duplicate_fragment_input_names(
    tmp_path: pathlib.Path,
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    dataset = configuration["entities"]["pump_telemetry"]["datasets"]["pump_telemetry_dataset"]
    dataset["actions"]["duplicate_input"] = {
        "binding": dataset["actions"]["read_pump_telemetry"]["binding"],
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
    configuration["entities"]["pump_telemetry"]["datasets"]["pump_telemetry_dataset"]["actions"][
        "read_pump_telemetry"
    ]["features"]["outputs"].remove("$features.plant")
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(configuration), encoding="utf-8")

    spec.load_spec(spec_path)


def test_spec_validation_rejects_unknown_vectorize_template(
    tmp_path: pathlib.Path,
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["entities"]["pump_telemetry"]["datasets"]["pump_telemetry_dataset"]["actions"][
        "recommended_flow_rate"
    ]["binding"]["function"] = "missing_vectorize_template"
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
    dataset = configuration["entities"]["pump_telemetry"]["datasets"]["pump_telemetry_dataset"]
    collision = json.loads(json.dumps(dataset["actions"]["converged"]))
    dataset["actions"]["pump_collision"] = {
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
    calculation = json.loads(
        json.dumps(
            configuration["entities"]["pump"]["datasets"]["pump_dataset"]["actions"][
                "health_signal_normalized"
            ]
        )
    )
    calculation["features"]["outputs"] = ["$features.health_signal_normalized_copy"]
    copied_feature = configuration["entities"]["pump"]["datasets"]["pump_dataset"]["features"][
        "health_signal_normalized"
    ]
    configuration["entities"]["pump_copy"] = {
        "name": "Pump copy",
        "dimensions": ["pump"],
        "datasets": {
            "pump_copy_dataset": {
                "row_scope": {"grain": "", "filtering": "", "coverage": ""},
                "features": {"health_signal_normalized_copy": copied_feature},
                "actions": {"health_signal_normalized_copy": calculation},
            }
        },
    }
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(configuration), encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="cannot read feature .* from another dataset",
    ):
        spec.load_spec(spec_path)
