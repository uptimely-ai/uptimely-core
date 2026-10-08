import json
import re
from pathlib import Path

from uptimely.compile import Compiler

SPEC_PATH = Path("examples/example_1/generated/spec/spec.json")


def test_compiled_plan_export_omits_generated_timestamp(tmp_path: Path) -> None:
    plan = Compiler(SPEC_PATH).compile()

    output_path = plan.export_json(tmp_path / "execution_plan.json")
    metadata = json.loads(output_path.read_text(encoding="utf-8"))

    assert "generated_at" not in metadata
    assert [stage["stage"] for stage in metadata["execution_stages"]] == list(
        range(1, len(metadata["execution_stages"]) + 1)
    )
    assert [
        step["position"] for stage in metadata["execution_stages"] for step in stage["steps"]
    ] == list(range(1, metadata["callable_count"] + 1))
    assert all(
        "feature" in step
        and "depends_on_callables" in step
        and "callable_type" in step
        and "title" in step
        and "entrypoint" in step
        for stage in metadata["execution_stages"]
        for step in stage["steps"]
    )
    assert {step["operation_type"] for step in metadata["execution_order"]} == {
        "read",
        "collapse",
        "vectorize",
        "write",
    }
    assert {step["callable_type"] for step in metadata["execution_order"]} == {
        "read",
        "collapse",
        "vectorize",
        "write",
    }
    aggregate_step = next(
        step for step in metadata["execution_order"] if step["function"] == "aggregate_by_dimension"
    )
    assert aggregate_step["entity"] == "pump"
    assert aggregate_step["args"]["dataset"]["value"] == "pump_telemetry_dataset"
    assert all(
        value.get("value") != "$current"
        for operation in plan.operations
        for value in operation.arguments.values()
        if isinstance(value, dict) and "value" in value
    )
    assert aggregate_step["args"]["dimensions"]["value"] == [
        "plant",
        "production_line",
        "pump",
    ]
    assert aggregate_step["returns"]["type"] == {"engine": "LazyFrame"}
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

    assert report_path == Path("generated/compile/execution_plan.html")
    assert report_path.is_file()
