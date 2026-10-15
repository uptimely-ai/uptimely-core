import json
import pathlib
import re
import sys

import pytest

from uptimely import compile, spec
from uptimely.cli import cli
from uptimely.explorer import explorer

SPEC_PATH = pathlib.Path("examples/pump_analytics/_generated/spec/spec.json")


def test_execution_plan_cli_exports_only_json(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "uptimely",
            "plan",
            "build",
            "--spec",
            str(SPEC_PATH),
            "--output",
            str(tmp_path / "compile" / "execution_plan.json"),
        ],
    )
    cli.main()

    assert {path.name for path in (tmp_path / "compile").iterdir()} == {"execution_plan.json"}


def test_compiled_plan_export_omits_generated_timestamp(tmp_path: pathlib.Path) -> None:
    plan = compile.Compiler(SPEC_PATH).compile()

    output_path = plan.export_json(tmp_path / "execution_plan.json")
    metadata = json.loads(output_path.read_text(encoding="utf-8"))

    assert metadata == plan.plan.to_dict()
    assert set(metadata) == {
        "plan_version",
        "specification_version",
        "required_backend",
        "resources",
        "operations",
        "stages",
    }
    assert {operation["kind"] for operation in metadata["operations"]} == {
        "read",
        "collapse",
        "vectorize",
        "write",
    }
    collapse_operation = next(
        operation for operation in metadata["operations"] if operation["kind"] == "collapse"
    )
    assert collapse_operation["entity_id"] == "pump"
    assert collapse_operation["entrypoint"].endswith(":maximum")
    assert collapse_operation["arguments"] == {
        "feature": "bearing_temperature",
        "dataset": "pump_telemetry_dataset",
        "dimensions": ["plant", "production_line", "pump"],
        "output": "bearing_temperature_max",
    }
    assert collapse_operation["output_features"] == [
        "plant",
        "production_line",
        "pump",
        "bearing_temperature_max",
    ]


def test_execution_plan_report_shows_topology_stages(tmp_path: pathlib.Path) -> None:
    explorer.Explorer(spec.Specification.from_json(SPEC_PATH)).create_html(tmp_path / "index.html")
    report_path = tmp_path / "plan/stages.html"
    report = report_path.read_text(encoding="utf-8")

    assert "<title>Plan Stages</title>" in report
    assert ">Stages</span></h1>" in report
    assert "Stage 1" in report
    assert "parallel operations" in report
    assert ">Operation</dt>" in report
    assert ">Callable type</dt>" in report
    assert ">Produces</dt>" in report
    assert ">Depends on callables</dt>" in report
    assert ">Returns</dt>" in report
    assert ">health_signal_normalized</dd>" in report
    assert "md:grid-cols-[8rem_minmax(0,1fr)_minmax(0,1fr)_10rem]" in report
    assert "md:col-span-4" in report
    assert ">Maximum</h3>" in report
    assert "Open Python module" in report
    assert "No callable dependencies" in report
    assert "maximum</span>" in report
    source_match = re.search(r'href="([^"]*functions/calculation\.py)"', report)
    assert source_match is not None
    assert (report_path.parent / source_match.group(1)).resolve().is_file()

    report = (tmp_path / "plan/graph.html").read_text(encoding="utf-8")
    assert 'id="callable-graph"' in report
    assert "3d-force-graph" in report
    assert "Callable details" in report
    assert '"node_type": "callable"' in report
    assert '"operation_type": "read"' in report
    assert '"operation_type": "collapse"' in report
    assert '"operation_type": "vectorize"' in report
    assert '"operation_type": "write"' in report
    assert '"callable_type": "read"' in report
    assert '"callable_type": "vectorize"' in report
    assert '"callable_type": "write"' in report
    assert "Execution graph legend" in report
    assert "Vectorize function</span>" in report
    assert "Write function</span>" in report
    assert (
        '"source": "callable:collapse:maximum:'
        'pump:pump_dataset:bearing_temperature_by_pump"' in report
    )
    assert (
        '"target": "callable:vectorize:normalize_health_signal:'
        'pump:pump_dataset:health_signal_normalized"' in report
    )
    assert "OctahedronGeometry" in report


def test_website_exports_plan_pages_to_default_path(tmp_path: pathlib.Path, monkeypatch) -> None:
    specification = spec.Specification.from_json(SPEC_PATH)
    monkeypatch.chdir(tmp_path)

    index = explorer.Explorer(specification).create_html()

    assert index == pathlib.Path("_generated/explorer/index.html")
    for filename in (
        "plan/overview.html",
        "plan/graph.html",
        "plan/stages.html",
    ):
        assert (index.parent / filename).is_file()
    assert not pathlib.Path("_generated/compile").exists()
