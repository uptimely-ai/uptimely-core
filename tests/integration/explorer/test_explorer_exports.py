"""Tests for Explorer exports."""

import ast
import json
import pathlib
import re

import pytest
from conftest import EXAMPLES_ROOT, engine_for_plan, render_explorer

from uptimely import compiler, spec
from uptimely.explorer import graph_render, spec_render
from uptimely.spec import operations

SPEC_PATH = EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json"
REFERENCE_PATH = pathlib.Path("docs/components/spec.md")
OBSERVATION_TOTALS_PATH = pathlib.Path("tests/fixtures/spec/observation_totals.json")


@pytest.mark.parametrize(
    ("language", "snippet"),
    re.findall(r"```(json|python)\n(.*?)\n```", REFERENCE_PATH.read_text(), re.DOTALL),
)
def test_spec_reference_snippet_syntax(language: str, snippet: str) -> None:
    if language == "python":
        ast.parse(snippet)
    else:
        document = "{" + snippet + "}" if snippet.lstrip().startswith('"') else snippet
        json.loads(document)


def test_spec_json_parses_compiles_and_executes() -> None:
    spec_definition = spec.load_spec(OBSERVATION_TOTALS_PATH)
    compiled = compiler.Compiler().compile(spec_definition, features=["total"])
    execution = engine_for_plan(compiled, spec_definition=spec_definition).run()

    assert len(compiled.invocations) == 2
    assert not execution.failures
    assert execution.datasets["observations"].sort("id").select("id", "total").rows() == [
        (1, 3),
        (2, 7),
    ]


def test_reference_exports_to_default_directory(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    monkeypatch.chdir(tmp_path)
    document_path = render_explorer(spec_definition)
    expected = pathlib.Path("_generated/explorer/index.html")
    assert document_path == expected
    assert document_path.is_file()
    assert not pathlib.Path("generated").exists()
    assert not list(tmp_path.rglob("*.json"))


def test_html_export_preserves_spec_definition(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    monkeypatch.chdir(tmp_path)
    spec_path = pathlib.Path("_generated/build/spec.json")
    spec.write_document(spec_definition, spec_path)
    original = spec_path.read_bytes()

    output = render_explorer(spec_definition)

    assert output == pathlib.Path("_generated/explorer/index.html")
    assert spec_path.read_bytes() == original
    assert list(tmp_path.rglob("*.json")) == [tmp_path / spec_path]


def test_build_spec_context() -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    context = spec_render._build_context(spec_definition, False)

    datasets = context.configuration["entities"]["pump_telemetry"]["datasets"]
    assert list(datasets) == ["pump_telemetry_dataset"]
    assert "id" not in datasets["pump_telemetry_dataset"]
    assert (
        context.configuration["dimensions"]["plant"]["description"]
        == "Manufacturing plant identifier"
    )
    assert context.summary.entity_count == 2
    assert context.summary.dataset_count == 3
    assert sorted(context.summary.function_buckets) == sorted(operations.FUNCTION_KINDS)
    assert context.summary.function_buckets == {
        operation: sum(
            function.kind == operation for function in spec_definition.functions.root.values()
        )
        for operation in operations.FUNCTION_KINDS
    }
    assert context.summary.function_buckets["escape"] == 1
    assert context.feature_dependencies
    assert context.generated_at is None


def test_escape_declarations_are_explicit_in_explorer_views(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["functions"]["external_audit"] = {
        "kind": "escape",
        "returns": "any",
        "entrypoint": "examples.pump_analytics.functions.analytics:maximum",
        "args": {},
        "description": "Send an audit record to an external service.",
    }
    dataset = configuration["entities"]["pump_telemetry"]["datasets"]["pump_telemetry_dataset"]
    dataset["features"]["audit_reference"] = {"type": "string"}
    dataset["features"]["audit_status"] = {"type": "string"}
    dataset["features"]["audit_followup"] = {"type": "string"}
    dataset["mappings"]["external_audit"] = {
        "binding": {"function": "external_audit", "args": {}},
        "features": {
            "inputs": ["$features.bearing_temperature", "$features.vibration_rms"],
            "outputs": ["$features.audit_reference", "$features.audit_status"],
        },
    }
    dataset["mappings"]["external_audit_followup"] = {
        "binding": {"function": "external_audit", "args": {}},
        "features": {
            "inputs": ["$features.audit_reference"],
            "outputs": ["$features.audit_followup"],
        },
    }
    spec_path = tmp_path / "escape-spec.json"
    spec_path.write_text(json.dumps(configuration), encoding="utf-8")
    definition = spec.load_spec(spec_path)
    plan = compiler.Compiler().compile(definition)

    context = spec_render._build_context(definition, False)
    assert context.summary.function_buckets["escape"] == 2
    assert context.summary.feature_buckets["external"] == 4
    assert all(
        {
            "function": "external_audit",
            "kind": "escape",
            "feature": output,
            "dependencies": ["bearing_temperature", "vibration_rms"],
        }
        in context.feature_dependencies
        for output in ("audit_reference", "audit_status")
    )
    assert {
        "function": "external_audit",
        "kind": "escape",
        "feature": "audit_followup",
        "dependencies": ["audit_reference"],
    } in context.feature_dependencies
    function = context.configuration["functions"]["external_audit"]
    assert function["declared_returns"] == "any"
    assert function["escape_mappings"] == [
        {
            "entity": "pump_telemetry",
            "dataset": dataset.get("id", "pump_telemetry_dataset"),
            "mapping": "external_audit",
            "inputs": ["bearing_temperature", "vibration_rms"],
            "outputs": ["audit_reference", "audit_status"],
        },
        {
            "entity": "pump_telemetry",
            "dataset": dataset.get("id", "pump_telemetry_dataset"),
            "mapping": "external_audit_followup",
            "inputs": ["audit_reference"],
            "outputs": ["audit_followup"],
        },
    ]
    escape_invocations = [
        invocation for invocation in plan.invocations if invocation.function_kind == "escape"
    ]
    assert len(escape_invocations) == 3
    first_escape = next(
        invocation for invocation in escape_invocations if invocation.mapping_id == "external_audit"
    )
    followup_escape = next(
        invocation
        for invocation in escape_invocations
        if invocation.mapping_id == "external_audit_followup"
    )
    assert first_escape.id in followup_escape.dependency_ids

    index = render_explorer(definition, tmp_path / "site/index.html", plan=plan)
    feature_page = (index.parent / "spec/features.html").read_text(encoding="utf-8")
    datasets_page = (index.parent / "spec/datasets.html").read_text(encoding="utf-8")
    functions_page = (index.parent / "spec/functions.html").read_text(encoding="utf-8")
    graph_page = (index.parent / "spec/graph.html").read_text(encoding="utf-8")
    plan_page = (index.parent / "plan/graph.html").read_text(encoding="utf-8")
    stages_page = (index.parent / "plan/stages.html").read_text(encoding="utf-8")
    lineage_page = (index.parent / "execution/data_lineage.html").read_text(encoding="utf-8")

    assert "Declared external output; not a verified dataframe column." in feature_page
    assert "Declared inputs: $features.bearing_temperature, $features.vibration_rms" in feature_page
    assert (
        "Escape outputs are declared external features, not verified or materialized "
        "dataset columns." in datasets_page
    )
    assert "Uncontrolled external operation" in functions_page
    assert "Python return value is ignored" in functions_page
    assert "External outputs: audit_reference, audit_status" in functions_page
    assert "Declares external outputs" in (index.parent / "js/feature_graph.js").read_text(
        encoding="utf-8"
    )
    assert '"function_kind": "escape"' in graph_page
    assert '"features": ["audit_reference", "audit_status"]' in graph_page
    assert '"features": ["audit_followup"]' in graph_page
    assert "Declares external outputs" in (index.parent / "js/invocation_graph.js").read_text(
        encoding="utf-8"
    )
    assert "audit_reference, audit_status" in plan_page
    assert '"input_features": ["bearing_temperature", "vibration_rms"]' in plan_page
    assert "Declares external outputs" in stages_page
    assert "not verified or materialized as dataframe columns" in stages_page
    escape_steps = re.findall(
        r'<article class="lineage-step"[^>]*data-operation="escape".*?</article>',
        lineage_page,
        re.DOTALL,
    )
    assert len(escape_steps) == 3
    escape_step = next(step for step in escape_steps if "audit_reference, audit_status" in step)
    assert "Declared feature inputs" in escape_step
    assert "Declared external outputs" in escape_step
    assert "not materialized as dataframe columns" in escape_step
    assert "External declaration; no materialized result" in escape_step
    assert 'data-side="output"' not in escape_step
    followup_step = next(
        step for step in escape_steps if "Declared feature inputs</strong>audit_reference" in step
    )
    assert re.search(r'data-dependencies="[^"]+"', followup_step)

    graph_nodes, graph_links = graph_render.graph_payload_from_cytoscape(
        spec.FeatureGraph(definition)
    )
    audit_feature_nodes = {
        node["label"]: node
        for node in graph_nodes
        if node.get("label") in {"audit_reference", "audit_status", "audit_followup"}
    }
    assert set(audit_feature_nodes) == {"audit_reference", "audit_status", "audit_followup"}
    assert all(node.get("data_type") == "string" for node in audit_feature_nodes.values())
    assert all(node.get("is_source_input") is not True for node in audit_feature_nodes.values())
    assert {(link["source"], link["target"]) for link in graph_links} >= {
        ("function:escape:external_audit:external_audit", "audit_reference"),
        ("function:escape:external_audit:external_audit", "audit_status"),
        ("audit_reference", "function:escape:external_audit:external_audit_followup"),
        (
            "function:escape:external_audit:external_audit_followup",
            "audit_followup",
        ),
    }


def test_generate_html_explorer(tmp_path: pathlib.Path, monkeypatch) -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    monkeypatch.chdir(tmp_path)

    document_path = render_explorer(spec_definition)
    pages = {
        filename: (document_path.parent / filename).read_text(encoding="utf-8")
        for filename in (
            "spec/overview.html",
            "spec/features.html",
            "spec/datasets.html",
            "spec/dimensions.html",
            "spec/functions.html",
        )
    }
    document = "\n".join(pages.values())

    assert document_path.name == "index.html"
    assert not document_path.with_suffix(".json").exists()
    for filename in pages:
        assert f'href="../{filename}"' in document
    assert ">Features<" in document
    assert "Datasets" in document
    assert "Mappings" in document
    assert ">source<" in document
    assert "space-y-5" in document
    for filename, section in (
        ("spec/overview.html", "overview"),
        ("spec/features.html", "entities"),
        ("spec/dimensions.html", "dimensions"),
        ("spec/functions.html", "functions"),
    ):
        assert f'id="{section}"' in pages[filename]
    assert "Pump telemetry" in document
    assert "pump_telemetry_dataset" in document
    assert "Manufacturing plant identifier" in document
    assert "discharge_pressure" in document
    assert "maximum" in document
    assert "normalize_health_signal" in document
    assert "examples.pump_analytics.functions.analytics:maximum" in document
    assert "examples/pump_analytics/functions/analytics.py" in document
    assert "file:///" in document
    assert "-&gt; LazyFrame" in document
    assert "-&gt; LazyFrame" in document
    assert "read · read_pump_telemetry" in document
    assert document.index("Pump telemetry") < document.index(
        "rounded-2xl border border-slate-800 bg-slate-900/70 p-6"
    )
    assert "pump" in document
    assert ">Overview<" in document
    assert ">source<" in document
    assert "mt-5 border-t border-slate-800 pt-4" in document
    for group_name in ("vectorize", "read", "write"):
        assert f'data-function-group="{group_name}"' in document
    assert "Vectorize" in document
    assert "Read" in document
    assert "Write" in document
    assert 'data-function-group="collapse"' in document
    assert "Functions wrapped in grouping by the target entity dimensions" in document
    assert "Collapse function" in document


def test_generate_html_explorer_from_in_memory_spec_is_deterministic(
    tmp_path: pathlib.Path,
) -> None:
    spec_definition = spec.load_spec(SPEC_PATH)

    first_path = render_explorer(spec_definition, output_path=tmp_path / "first" / "index.html")
    second_path = render_explorer(spec_definition, output_path=tmp_path / "second" / "index.html")

    for first_page in first_path.parent.rglob("*.html"):
        relative_path = first_page.relative_to(first_path.parent)
        assert first_page.read_bytes() == (second_path.parent / relative_path).read_bytes()
        assert "generated_at" not in first_page.read_text(encoding="utf-8")
