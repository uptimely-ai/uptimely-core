import json
import pathlib
import re
import shutil
import sys

import pytest
from conftest import EXAMPLES_ROOT, example_bundle, render_explorer

from uptimely import execution_plan, project, spec
from uptimely.cli import cli

REPOSITORY_ROOT = pathlib.Path(__file__).parents[2]
EXAMPLE_ROOT = EXAMPLES_ROOT / "pump_analytics"
SPEC_PATH = EXAMPLE_ROOT / "_generated/build/spec.json"


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
    assert (bundle / "explorer/index.html").is_file()
    assert not (project_root / "_generated/spec/spec.json").exists()
    assert not (project_root / "_generated/compile/execution_plan.json").exists()


def test_compiled_plan_export_omits_generated_timestamp(tmp_path: pathlib.Path) -> None:
    plan = example_bundle().execution_plan

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
    assert metadata["plan_version"] == 3
    assert {invocation["function_kind"] for invocation in metadata["invocations"]} == {
        "read",
        "collapse",
        "vectorize",
        "write",
        "escape",
    }
    collapse_invocation = next(
        invocation
        for invocation in metadata["invocations"]
        if invocation["function_kind"] == "collapse"
    )
    assert collapse_invocation["entity_id"] == "pump"
    assert collapse_invocation["entrypoint"].endswith(":maximum")
    assert collapse_invocation["arguments"] == {
        "feature": "bearing_temperature",
        "dataset": "pump_telemetry_dataset",
        "dimensions": ["plant", "production_line", "pump"],
        "output": "bearing_temperature_max",
    }
    assert collapse_invocation["output_features"] == [
        "plant",
        "production_line",
        "pump",
        "bearing_temperature_max",
    ]


def test_execution_plan_report_shows_topology_stages(tmp_path: pathlib.Path) -> None:
    render_explorer(spec.load_spec(SPEC_PATH), tmp_path / "index.html")
    report_path = tmp_path / "plan/stages.html"
    report = report_path.read_text(encoding="utf-8")

    assert "<title>Plan Stages</title>" in report
    assert ">Stages</span></h1>" in report
    assert "Stage 1" in report
    assert "parallel invocations" in report
    assert ">Function kind</dt>" in report
    assert ">Function</dt>" in report
    assert ">Produces</dt>" in report
    assert ">Depends on invocations</dt>" in report
    assert ">Returns</dt>" in report
    assert ">health_signal_normalized</dd>" in report
    assert "md:grid-cols-[8rem_minmax(0,1fr)_minmax(0,1fr)_10rem]" in report
    assert "md:col-span-4" in report
    assert ">Maximum</h3>" in report
    assert "Open Python module" in report
    assert "No invocation dependencies" in report
    assert "maximum</span>" in report
    source_match = re.search(r'href="([^"]*functions/analytics\.py)"', report)
    assert source_match is not None
    assert (report_path.parent / source_match.group(1)).resolve().is_file()

    report = (tmp_path / "plan/invocation_lineage.html").read_text(encoding="utf-8")
    assert 'id="invocation-lineage-graph"' in report
    assert "3d-force-graph" in report
    assert "Invocation details" in report
    assert '"node_type": "invocation"' in report
    assert '"function_kind": "read"' in report
    assert '"function_kind": "collapse"' in report
    assert '"function_kind": "vectorize"' in report
    assert '"function_kind": "write"' in report
    assert "<summary>Legend</summary>" in report
    assert 'class="function"' not in report
    assert '"source": "invocation:maximum:pump:pump_dataset:bearing_temperature_by_pump"' in report
    assert (
        '"target": "invocation:normalize_health_signal:'
        'pump:pump_dataset:health_signal_normalized"' in report
    )
    invocation_script = (tmp_path / "js/invocation_lineage.js").read_text(encoding="utf-8")
    shared_script = (tmp_path / "js/graph_components.js").read_text(encoding="utf-8")
    assert "ExplorerGraph.datasetNodeObject(node, node.function_id, style)" in invocation_script
    assert "SphereGeometry" in shared_script


def test_website_exports_plan_pages_to_default_path(tmp_path: pathlib.Path, monkeypatch) -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    monkeypatch.chdir(tmp_path)

    index = render_explorer(spec_definition)

    assert index == pathlib.Path("_generated/explorer/index.html")
    for filename in (
        "plan/overview.html",
        "plan/invocation_lineage.html",
        "plan/stages.html",
    ):
        assert (index.parent / filename).is_file()
    assert not pathlib.Path("_generated/compile").exists()
