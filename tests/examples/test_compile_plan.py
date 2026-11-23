import json
import pathlib
import shutil
import sys

import pytest
from support import examples as example_support

from uptimely import application
from uptimely import plan as execution_plan
from uptimely.cli import cli
from uptimely.explorer.sections import spec as explorer_spec
from uptimely.spec.feature_graph import feature_graph

REPOSITORY_ROOT = pathlib.Path(__file__).parents[2]
EXAMPLE_ROOT = example_support.EXAMPLES_ROOT


def test_telemetry_relations_are_identifiers_not_features(
    pump_bundle: application.BuildBundle,
) -> None:
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
        if invocation.semantics.profile_id == "pump_telemetry"
        and invocation.semantics.operator_id == "read_pump_telemetry"
        and invocation.semantics.role == "compute"
    )
    assert invocation.semantics.target_identifiers == ["pump_id", "timestamp"]
    assert relations.issubset(invocation.semantics.fragment_keys)
    assert not relations.intersection(invocation.semantics.output_features)
    for key, operator in document.operator_items:
        assert not document.key_ids.intersection(operator.input_features)
        assert not document.key_ids_by_profile[key[0]].intersection(operator.output_features)
    raw, calculated, _ = explorer_spec._feature_data(document)
    assert not relations.intersection(item["id"] for item in [*raw, *calculated])
    graph = feature_graph.FeatureGraph(document)
    assert not relations.intersection(item.name for item in graph.feature_nodes)


def test_hourly_warning_aggregates_all_measurements_in_one_operator(
    pump_bundle: application.BuildBundle,
) -> None:
    profile_id = "pump_telemetry_by_hour_when_warning"
    invocations = [
        invocation
        for invocation in pump_bundle.execution_plan.invocations
        if invocation.semantics.profile_id == profile_id
        and invocation.semantics.function_id == "aggregate"
    ]

    assert len(invocations) == 1
    invocation = invocations[0]
    assert set(invocation.semantics.input_features) == {
        "warning_differential_pressure",
        "warning_flow_rate",
        "warning_motor_power",
        "warning_bearing_temperature",
        "warning_vibration_rms",
    }
    assert set(invocation.semantics.output_features) == {
        "warning_hour_mean_differential_pressure",
        "warning_hour_mean_flow_rate",
        "warning_hour_mean_motor_power",
        "warning_hour_max_bearing_temperature",
        "warning_hour_max_vibration_rms",
    }
    assert invocation.arguments["aggregations"] == {
        "warning_differential_pressure": "mean",
        "warning_flow_rate": "mean",
        "warning_motor_power": "mean",
        "warning_bearing_temperature": "max",
        "warning_vibration_rms": "max",
    }


def test_compiled_invocations_capture_runtime_contracts(
    pump_bundle: application.BuildBundle,
) -> None:
    document = pump_bundle.spec_definition
    restored = execution_plan.from_dict(execution_plan.to_dict(pump_bundle.execution_plan))

    for invocation in restored.invocations:
        grain_keys = document.identifiers_by_profile[invocation.semantics.profile_id]
        profile = document.profiles[invocation.semantics.profile_id]
        assert invocation.semantics.target_identifiers == grain_keys
        assert invocation.semantics.column_types == {
            **{
                name: feature.type
                for name, feature in profile.features.items()
                if feature.type is not None
            },
            **document.identifier_types_by_profile[invocation.semantics.profile_id],
            **document.relation_types_by_profile[invocation.semantics.profile_id],
        }
        assert invocation.semantics.fragment_keys == list(
            document.key_types_by_profile[invocation.semantics.profile_id]
        )
        assert invocation.semantics.argument_types == {
            name: argument.type
            for name, argument in document.functions[invocation.semantics.function_id].args.items()
        }


def test_each_profile_publishes_its_features_with_the_shared_writer(
    pump_bundle: application.BuildBundle,
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
                "mode",
                "pressure_flow_efficiency",
                "room_temperature_reference",
                "bearing_temperature_rise",
                "bearing_temperature_delta",
                "vibration_delta",
                "pump_health_score",
                "pump_mode",
            },
            "pump_telemetry_output",
        ),
        "pump_telemetry_by_minute": (
            {"bearing_temperature_minute_max"},
            "pump_telemetry_by_minute_output",
        ),
        "pump_telemetry_by_hour_when_warning": (
            {
                "warning_hour_mean_differential_pressure",
                "warning_hour_mean_flow_rate",
                "warning_hour_mean_motor_power",
                "warning_hour_max_bearing_temperature",
                "warning_hour_max_vibration_rms",
                "operating_point_recommendation",
                "recommended_flow_rate",
                "recommended_differential_pressure",
                "energy_cost_score",
                "converged",
            },
            "pump_telemetry_by_hour_when_warning_output",
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
            if (
                invocation.semantics.profile_id == profile_id
                and invocation.semantics.function_id == "write_file"
                and invocation.semantics.is_sink
            )
        )
        assert writer.semantics.function_id == "write_file"
        assert set(writer.arguments["features"]) == feature_ids
        assert writer.arguments["output"] == f"$paths.{output_path}"

    assert not any(
        invocation.semantics.profile_id == "pump_telemetry_when_warning"
        and invocation.semantics.function_id == "write_file"
        and invocation.semantics.is_sink
        for invocation in pump_bundle.execution_plan.invocations
    )


@pytest.mark.usefixtures("example_projects")
def test_project_build_cli_exports_complete_bundle(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "example"
    shutil.copytree(
        EXAMPLE_ROOT,
        project_root,
        ignore=shutil.ignore_patterns("artifacts", "__pycache__"),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "uptimely",
            "build",
            "--project-root",
            str(project_root),
        ],
    )
    cli.main()

    bundle = project_root / application.BUILD_OUTPUT_DIR
    assert (bundle / "build.json").is_file()
    assert (bundle / "spec.json").is_file()
    assert (bundle / "plan.json").is_file()
    saved_plan = json.loads((bundle / "plan.json").read_text(encoding="utf-8"))
    assert saved_plan["invocations"]
    assert all(
        set(invocation) == {"id", "entrypoint", "arguments", "returns", "semantics"}
        for invocation in saved_plan["invocations"]
    )
    assert not (bundle / "explorer").exists()
    assert (project_root / application.EXPLORER_DATA_FILE).is_file()
    assert not (project_root / "artifacts/spec/spec.json").exists()
    assert not (project_root / "artifacts/compile/execution_plan.json").exists()


def test_compiled_plan_export_omits_generated_timestamp(
    tmp_path: pathlib.Path, pump_bundle: application.BuildBundle
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
        "datasets",
    }
    assert metadata["plan_version"] == execution_plan.PLAN_VERSION
    assert all(
        "operator_kind" not in invocation["semantics"] for invocation in metadata["invocations"]
    )
    assert {invocation["semantics"]["role"] for invocation in metadata["invocations"]} == {
        "compute",
        "merge",
    }
    collapse_invocation = next(
        invocation
        for invocation in metadata["invocations"]
        if invocation["semantics"]["operator_id"] == "bearing_temperature_by_pump"
    )
    assert "entity_id" not in collapse_invocation
    assert collapse_invocation["entrypoint"].endswith(":aggregate")
    arguments = collapse_invocation["arguments"]
    assert {key: value for key, value in arguments.items() if key != "dataset"} == {
        "aggregations": {"bearing_temperature": "max"},
        "dimensions": ["pump_id"],
        "rename": {"bearing_temperature": "bearing_temperature_max"},
    }
    dataset_reference = arguments["dataset"]
    assert any(invocation["returns"] == dataset_reference for invocation in metadata["invocations"])
    assert collapse_invocation["semantics"]["output_features"] == ["bearing_temperature_max"]


def test_build_plan_contains_calls_and_nested_invocation_semantics(
    pump_bundle: application.BuildBundle,
) -> None:
    plan_data = json.loads(pump_bundle.execution_plan_path.read_text(encoding="utf-8"))

    assert set(plan_data) == {
        "plan_version",
        "required_backend",
        "invocations",
        "stages",
        "datasets",
    }
    assert [list(stage) for stage in plan_data["stages"]] == [
        stage.invocation_ids for stage in pump_bundle.execution_plan.stages
    ]
    assert all(
        set(invocation) == {"id", "entrypoint", "arguments", "returns", "semantics"}
        for invocation in plan_data["invocations"]
    )
    for invocation in plan_data["invocations"]:
        result = invocation["semantics"]["result"]
        if result == "none":
            assert invocation["returns"] is None
            continue
        prefix = {
            "merge": "$dataset",
            "fragment": "$fragments",
            "target": "$datasets",
        }[invocation["semantics"]["role"] if invocation["semantics"]["role"] == "merge" else result]
        assert invocation["returns"].startswith(
            f"{prefix}.{invocation['semantics']['profile_id']}."
        )
    assert all(
        "target_identifiers" in invocation["semantics"]
        and "column_types" in invocation["semantics"]
        for invocation in plan_data["invocations"]
    )
