import json
import pathlib
import shutil
import sys

import pytest
from support import examples as example_support

from uptimely import execution_plan, project
from uptimely.cli import cli

REPOSITORY_ROOT = pathlib.Path(__file__).parents[2]
EXAMPLE_ROOT = example_support.EXAMPLES_ROOT / "pump_analytics"


def test_compiled_invocations_capture_runtime_contracts(pump_bundle: project.BuildBundle) -> None:
    document = pump_bundle.spec_definition
    restored = execution_plan.from_dict(execution_plan.to_dict(pump_bundle.execution_plan))

    for invocation in restored.invocations:
        grain_keys = document.grain_keys_by_profile[invocation.dataset_id]
        profile = document.profiles[invocation.dataset_id]
        assert invocation.id_columns == grain_keys
        assert invocation.column_types == {
            **{
                name: feature.type
                for name, feature in profile.features.items()
                if feature.type is not None
            },
            **document.grain_key_types_by_profile[invocation.dataset_id],
        }
        assert invocation.argument_types == {
            name: argument.type
            for name, argument in document.functions[invocation.function_id].args.items()
        }


@pytest.mark.usefixtures("example_projects")
def test_project_build_cli_exports_complete_bundle(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    examples = tmp_path / "examples"
    examples.mkdir()
    shutil.copyfile(REPOSITORY_ROOT / "examples/__init__.py", examples / "__init__.py")
    project_root = examples / "pump_analytics"
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
    assert set(metadata["resources"]) == {"signatures", "entrypoint_packages"}
    assert "spec_version" not in metadata
    assert set(metadata) == {
        "plan_version",
        "required_backend",
        "resources",
        "invocations",
        "stages",
    }
    assert metadata["plan_version"] == 5
    assert {invocation["function_kind"] for invocation in metadata["invocations"]} == {
        "read",
        "collapse",
        "expand",
        "vectorize",
        "write",
        "escape",
    }
    collapse_invocation = next(
        invocation
        for invocation in metadata["invocations"]
        if invocation["function_kind"] == "collapse"
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
    assert collapse_invocation["output_features"] == ["pump_id", "bearing_temperature_max"]
