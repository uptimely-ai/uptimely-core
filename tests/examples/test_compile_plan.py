import json
import pathlib
import shutil
import sys

import pytest
from support import examples as example_support

from uptimely import plan as execution_plan
from uptimely import project
from uptimely.cli import cli
from uptimely.explorer.sections import spec as explorer_spec
from uptimely.spec.feature_graph import feature_graph

REPOSITORY_ROOT = pathlib.Path(__file__).parents[2]
EXAMPLE_ROOT = example_support.EXAMPLES_ROOT


def test_telemetry_relations_are_identifiers_not_features(pump_bundle: project.BuildBundle) -> None:
    document = pump_bundle.spec_definition
    telemetry = document.profiles["pump_telemetry"]
    relations = {
        "server_room_id",
        "data_center_id",
        "machine_series_id",
        "machine_category_id",
        "minute",
        "hour",
        "day",
    }
    assert len(telemetry.relations) == 7
    assert not relations.intersection(telemetry.features)
    invocation = next(
        invocation
        for invocation in pump_bundle.execution_plan.invocations
        if invocation.profile_id == "pump_telemetry"
        and invocation.operator_id == "read_pump_telemetry"
        and invocation.role == "compute"
    )
    assert invocation.target_identifiers == ["pump_id", "timestamp"]
    assert relations.issubset(invocation.fragment_keys)
    assert not relations.intersection(invocation.output_features)
    for key, operator in document.operator_items:
        assert not document.key_ids.intersection(operator.input_features)
        assert not document.key_ids_by_profile[key[0]].intersection(operator.output_features)
    raw, calculated, _ = explorer_spec._feature_data(document)
    assert not relations.intersection(item["id"] for item in [*raw, *calculated])
    graph = feature_graph.FeatureGraph(document)
    assert not relations.intersection(item.name for item in graph.feature_nodes)


def test_compiled_invocations_capture_runtime_contracts(pump_bundle: project.BuildBundle) -> None:
    document = pump_bundle.spec_definition
    restored = execution_plan.from_dict(execution_plan.to_dict(pump_bundle.execution_plan))

    for invocation in restored.invocations:
        grain_keys = document.identifiers_by_profile[invocation.profile_id]
        profile = document.profiles[invocation.profile_id]
        assert invocation.target_identifiers == grain_keys
        assert invocation.column_types == {
            **{
                name: feature.type
                for name, feature in profile.features.items()
                if feature.type is not None
            },
            **document.identifier_types_by_profile[invocation.profile_id],
            **document.relation_types_by_profile[invocation.profile_id],
        }
        assert invocation.fragment_keys == list(
            document.key_types_by_profile[invocation.profile_id]
        )
        assert invocation.argument_types == {
            name: argument.type
            for name, argument in document.functions[invocation.function_id].args.items()
        }


def test_each_profile_publishes_its_features_with_the_shared_writer(
    pump_bundle: project.BuildBundle,
) -> None:
    expected_outputs = {
        "constants": (
            {"gravity", "room_temperature"},
            "constants_output",
        ),
        "pump": (
            {
                "pump_max_capacity",
                "series_max_capacity",
                "category_max_capacity",
                "max_capacity",
                "measurement",
                "reference_value",
                "bearing_temperature_max",
                "health_signal_normalized",
            },
            "pump_output",
        ),
        "pump_category": (
            {"bearing_temperature_category_max", "max_capacity_category"},
            "pump_category_output",
        ),
        "pump_series": (
            {"bearing_temperature_series_max", "max_capacity_series"},
            "pump_series_output",
        ),
        "pump_telemetry": (
            {
                "differential_pressure",
                "flow_rate",
                "bearing_temperature",
                "vibration_rms",
                "motor_power",
                "operation_mode",
                "recommended_flow_rate",
                "recommended_differential_pressure",
                "energy_cost_score",
                "converged",
                "pressure_flow_efficiency",
                "room_temperature_reference",
                "bearing_temperature_rise",
                "bearing_temperature_delta",
                "vibration_delta",
                "pump_health_score",
                "operating_point_recommendation",
            },
            "pump_telemetry_output",
        ),
        "pump_telemetry_by_minute": (
            {"bearing_temperature_minute_max"},
            "pump_telemetry_by_minute_output",
        ),
        "pump_telemetry_by_hour": (
            {"bearing_temperature_hour_max"},
            "pump_telemetry_by_hour_output",
        ),
        "pump_telemetry_by_day": (
            {"bearing_temperature_day_max"},
            "pump_telemetry_by_day_output",
        ),
    }

    for profile_id, (feature_ids, output_path) in expected_outputs.items():
        writer = next(
            invocation
            for invocation in pump_bundle.execution_plan.invocations
            if invocation.profile_id == profile_id and invocation.operator_kind == "write"
        )
        assert writer.function_id == "write_file"
        assert set(writer.arguments["features"]) == feature_ids
        assert writer.arguments["output"] == f"$paths.{output_path}"


@pytest.mark.usefixtures("example_projects")
def test_project_build_cli_exports_complete_bundle(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "example"
    shutil.copytree(
        EXAMPLE_ROOT,
        project_root,
        ignore=shutil.ignore_patterns("_generated", "__pycache__"),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "uptimely",
            "project",
            "build",
            "--project-root",
            str(project_root),
        ],
    )
    cli.main()

    bundle = project_root / project.BUILD_OUTPUT_DIR
    assert (bundle / "build.json").is_file()
    assert (bundle / "spec.json").is_file()
    assert (bundle / "execution_plan.json").is_file()
    assert not (bundle / "explorer").exists()
    assert (project_root / project.EXPLORER_DATA_FILE).is_file()
    assert not (project_root / "_generated/spec/spec.json").exists()
    assert not (project_root / "_generated/compile/execution_plan.json").exists()


def test_compiled_plan_export_omits_generated_timestamp(
    tmp_path: pathlib.Path, pump_bundle: project.BuildBundle
) -> None:
    plan = pump_bundle.execution_plan

    output_path = execution_plan.export_json(plan, tmp_path / "execution_plan.json")
    metadata = json.loads(output_path.read_text(encoding="utf-8"))

    assert metadata == execution_plan.to_dict(plan)
    assert "spec_version" not in metadata
    assert set(metadata) == {
        "plan_version",
        "required_backend",
        "invocations",
        "stages",
    }
    assert metadata["plan_version"] == execution_plan.PLAN_VERSION
    assert {invocation["operator_kind"] for invocation in metadata["invocations"]} == {
        "read",
        "collapse",
        "expand",
        "vectorize",
        "write",
        "escape",
    }
    assert {invocation["role"] for invocation in metadata["invocations"]} == {"compute", "merge"}
    collapse_invocation = next(
        invocation
        for invocation in metadata["invocations"]
        if invocation["operator_kind"] == "collapse"
    )
    assert "entity_id" not in collapse_invocation
    assert collapse_invocation["entrypoint"].endswith(":aggregate")
    assert collapse_invocation["arguments"] == {
        "feature": "bearing_temperature",
        "method": "max",
        "dataset": "pump_telemetry",
        "dimensions": ["pump_id"],
        "output": "bearing_temperature_max",
    }
    assert collapse_invocation["output_features"] == ["bearing_temperature_max"]
