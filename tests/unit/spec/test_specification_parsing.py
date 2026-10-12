import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from uptimely.analytics import FeatureGraph
from uptimely.analytics.models import FeatureNode
from uptimely.spec import Call, Function, Specification, SpecificationParser
from uptimely.spec.validation import SpecificationError

SPEC_PATH = Path("examples/example_1/_generated/spec/spec.json")


def _write_configuration(tmp_path: Path, configuration: dict, name: str) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(configuration), encoding="utf-8")
    return path


def test_specification_rejects_unknown_fields(tmp_path: Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["unexpected"] = True

    with pytest.raises(ValidationError, match="unexpected"):
        Specification.from_json(_write_configuration(tmp_path, configuration, "unknown.json"))


def test_specification_accepts_top_level_name(tmp_path: Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["name"] = "Pump analytics"

    specification = Specification.from_json(
        _write_configuration(tmp_path, configuration, "named.json")
    )

    assert specification.name == "Pump analytics"


def test_specification_defaults_missing_source_to_manual(tmp_path: Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration.pop("source", None)

    specification = Specification.from_json(
        _write_configuration(tmp_path, configuration, "manual.json")
    )

    assert specification.source.name == "manual"
    assert specification.source.generated is False


@pytest.mark.parametrize("location", ["dataset", "row_scope"])
def test_specification_rejects_legacy_slice_ordering(tmp_path: Path, location: str) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    dataset = configuration["entities"]["pump_telemetry"]["datasets"][0]
    target = dataset if location == "dataset" else dataset["row_scope"]
    target["ordering"] = "plant, production_line, pump, timestamp"

    with pytest.raises(ValidationError, match="ordering"):
        Specification.from_json(
            _write_configuration(tmp_path, configuration, f"legacy-ordering-{location}.json")
        )


def test_specification_rejects_unsupported_version(tmp_path: Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["version"] = "9.9.9"

    with pytest.raises(ValidationError, match="version"):
        Specification.from_json(_write_configuration(tmp_path, configuration, "version.json"))


def test_specification_rejects_dimension_parent_cycles(tmp_path: Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["dimensions"]["plant"]["parent"] = "pump"

    with pytest.raises(ValueError, match="Dimension parent cycle.*plant"):
        Specification.from_json(_write_configuration(tmp_path, configuration, "cycle.json"))


def test_specification_rejects_duplicate_dataset_ids(tmp_path: Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    duplicate = dict(configuration["entities"]["pump"]["datasets"][0])
    configuration["entities"]["pump"]["datasets"].append(duplicate)

    with pytest.raises(ValueError, match="Duplicate dataset id.*pump_dataset"):
        Specification.from_json(_write_configuration(tmp_path, configuration, "datasets.json"))


def test_specification_errors_expose_stable_code_and_path(tmp_path: Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    duplicate = dict(configuration["entities"]["pump"]["datasets"][0])
    configuration["entities"]["pump_telemetry"]["datasets"].append(duplicate)

    with pytest.raises(SpecificationError) as error:
        Specification.from_json(_write_configuration(tmp_path, configuration, "datasets.json"))

    assert error.value.code == "duplicate_dataset_id"
    assert error.value.path == ("entities", "pump", "datasets", "pump_dataset")


def test_specification_rejects_unknown_write_function(tmp_path: Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    dataset = configuration["entities"]["pump_telemetry"]["datasets"][0]
    dataset["mappings"]["write_pump_telemetry"]["binding"]["function"] = "missing_write"

    with pytest.raises(ValueError, match="mappings reference unknown functions: missing_write"):
        Specification.from_json(_write_configuration(tmp_path, configuration, "write.json"))


def test_specification_rejects_undeclared_binding_arguments(tmp_path: Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    binding_args = configuration["entities"]["pump_telemetry"]["datasets"][0]["mappings"][
        "read_pump_telemetry"
    ]["binding"]["args"]
    binding_args["unexpected"] = "value"

    with pytest.raises(
        ValueError,
        match="Binding for function read_pump_telemetry has unknown arguments: unexpected",
    ):
        Specification.from_json(_write_configuration(tmp_path, configuration, "arguments.json"))


def test_feature_references_are_explicit_and_recursive() -> None:
    args = {
        "feature": "$features.bearing_temperature",
        "literal": "bearing_temperature_max",
        "nested": {"columns": ["$features.flow_rate", "$features.bearing_temperature"]},
    }

    assert SpecificationParser._resolve_feature_dependencies(args) == [
        "bearing_temperature",
        "flow_rate",
    ]
    assert SpecificationParser._replace_arg_placeholders(args, "telemetry") == {
        "feature": "bearing_temperature",
        "literal": "bearing_temperature_max",
        "nested": {"columns": ["flow_rate", "bearing_temperature"]},
    }


def test_feature_placeholder_resolves_to_bound_feature_id() -> None:
    args = {"output": "$features.@"}

    assert SpecificationParser._replace_arg_placeholders(args, "dataset", "calculated_feature") == {
        "output": "calculated_feature"
    }


def test_structural_references_compile_to_identifiers() -> None:
    args = {
        "current": "$datasets.@",
        "specific": "$datasets.pump_units",
        "dimension": "$dimensions.pump",
    }

    assert SpecificationParser._replace_arg_placeholders(args, "pump_telemetry_dataset") == {
        "current": "pump_telemetry_dataset",
        "specific": "pump_units",
        "dimension": "pump",
    }


def test_dataset_mappings_are_supported_in_entity_specs(tmp_path: Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    for entity in configuration["entities"].values():
        for dataset in entity.get("datasets", []):
            for mapping in dataset["mappings"].values():
                assert "source" not in mapping
                binding = mapping["binding"]
                assert all(
                    not (isinstance(arg, dict) and arg.get("type") == "dataset_ref")
                    for arg in binding.get("args", {}).values()
                )

    spec_path = tmp_path / "spec_dataset_test.json"
    spec_path.write_text(json.dumps(configuration), encoding="utf-8")

    specification = Specification.from_json(spec_path)
    assert specification.entities["pump_telemetry"].datasets


def test_system_and_subset_support_multiple_variables() -> None:
    specification = Specification.from_json(SPEC_PATH)
    assert len(specification.resolved_functions) == 8
    collapse = specification.entities["pump"].datasets[0].mappings["bearing_temperature_by_pump"]
    assert not hasattr(collapse, "source")
    assert collapse.binding.function == "maximum"
    assert collapse.binding.args["feature"] == "$features.bearing_temperature"
    system = FeatureGraph(specification)

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
        isinstance(node.reference, FeatureNode)
        and node.reference.is_input
        and node.reference.name == "bearing_temperature"
        for node in system.graph
    )
    assert "machine" not in system.input_names

    subset = system.subset(["health_signal_normalized"])

    assert subset.output_names == ["health_signal_normalized"]
    assert "health_signal_normalized" in subset.feature_names
    assert "bearing_temperature_max" in subset.intermediate_names


def test_specification_validation_rejects_missing_output_variables() -> None:
    specification = SpecificationParser()
    specification.functions = [
        Function(
            id="broken.function",
            type="python_function",
            return_type="num",
            info={},
        )
    ]
    specification.calls = [
        Call(
            function="broken.function",
            entity="temperature",
            feature="",
        )
    ]

    with pytest.raises(ValueError, match="Every call must define a non-empty output feature name"):
        specification.validate()


def test_specification_validation_rejects_duplicate_feature_names(tmp_path: Path) -> None:
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
        Specification.from_json(spec_path)


def test_specification_validation_rejects_duplicate_fragment_input_names(
    tmp_path: Path,
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["entities"]["pump_telemetry"]["datasets"][0]["mappings"]["duplicate_input"] = {
        "binding": {"function": "read_pump_telemetry", "args": {}},
        "features": ["bearing_temperature"],
    }
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(configuration), encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="Feature bearing_temperature is produced by multiple mappings",
    ):
        Specification.from_json(spec_path)


def test_specification_validation_requires_dimensions_in_every_mapping(
    tmp_path: Path,
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["entities"]["pump_telemetry"]["datasets"][0]["mappings"]["read_pump_telemetry"][
        "features"
    ].remove("plant")
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(configuration), encoding="utf-8")

    with pytest.raises(ValueError, match="must include dimension columns: plant"):
        Specification.from_json(spec_path)


def test_specification_validation_rejects_unknown_vectorize_template(tmp_path: Path) -> None:
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
        Specification.from_json(spec_path)


def test_specification_validation_rejects_feature_dimension_name_collision(tmp_path: Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    dataset = configuration["entities"]["pump_telemetry"]["datasets"][0]
    collision = json.loads(json.dumps(dataset["mappings"]["converged"]))
    dataset["mappings"]["pump_collision"] = {
        **collision,
        "features": ["pump"],
    }
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(configuration), encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="Calculated feature names cannot duplicate entity dimensions: pump",
    ):
        Specification.from_json(spec_path)


def test_specification_validation_rejects_cross_dataset_feature_dependency(
    tmp_path: Path,
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    calculation = configuration["entities"]["pump"]["datasets"][0]["mappings"].pop(
        "health_signal_normalized"
    )
    calculation["features"] = ["health_signal_normalized_copy"]
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
        Specification.from_json(spec_path)
