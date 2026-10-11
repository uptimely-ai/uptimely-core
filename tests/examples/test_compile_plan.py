import json
import re
from pathlib import Path

from uptimely.compile import Compiler

SPEC_PATH = Path("examples/example_1/_generated/spec/spec.json")


def test_compiled_plan_export_omits_generated_timestamp(tmp_path: Path) -> None:
    plan = Compiler(SPEC_PATH).compile()

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
    aggregate_operation = next(
        operation
        for operation in metadata["operations"]
        if operation["id"].split(":")[2] == "aggregate_by_dimension"
    )
    assert aggregate_operation["entity_id"] == "pump"
    assert aggregate_operation["arguments"]["dataset"] == "pump_telemetry_dataset"
    assert aggregate_operation["arguments"]["dimensions"] == [
        "plant",
        "production_line",
        "pump",
    ]
    assert "spec_type" not in json.dumps(metadata)
    assert "runtime_type" not in json.dumps(metadata)


def test_execution_plan_report_shows_topology_stages(tmp_path: Path) -> None:
    plan = Compiler(SPEC_PATH).compile()

    report_path = plan.export_html(tmp_path / "report.html")
    report = report_path.read_text(encoding="utf-8")

    assert "<title>Execution plan</title>" in report
    assert ">Execution plan</h1>" in report
    assert "Compilation report" not in report
    assert ">Operations</h2>" in report
    assert "Execution order" not in report
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
    assert ">Aggregate by dimension</h3>" in report
    assert "Open Python module" in report
    assert "No callable dependencies" in report
    assert "aggregate_by_dimension</span>" in report
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
    assert "Dataframe operation</span>" in report
    assert "Vectorize</span>" in report
    assert "Write</span>" in report
    assert (
        '"source": "callable:collapse:aggregate_by_dimension:'
        'pump:pump_dataset:bearing_temperature_by_pump"' in report
    )
    assert (
        '"target": "callable:vectorize:normalize_health_signal:'
        'pump:pump_dataset:health_signal_normalized"' in report
    )
    assert "OctahedronGeometry" in report
    source_match = re.search(r'href="([^"]*functions/calculation\.py)"', report)
    assert source_match is not None
    assert (report_path.parent / source_match.group(1)).resolve().is_file()


def test_execution_plan_exports_html_to_default_path(tmp_path: Path, monkeypatch) -> None:
    plan = Compiler(SPEC_PATH).compile()
    monkeypatch.chdir(tmp_path)

    report_path = plan.export_html()

    assert report_path == Path("_generated/compile/execution_plan.html")
    assert report_path.is_file()
