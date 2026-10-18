"""Tests for Explorer exports."""

import ast
import json
import pathlib
import re

import pytest
from conftest import render_explorer

from uptimely import compiler, engine, spec
from uptimely.explorer import spec_render

SPEC_PATH = pathlib.Path("examples/pump_analytics/_generated/spec/spec.json")
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
    compiled = compiler.Compiler(spec_definition, features=["total"]).compile()
    execution = engine.Engine(compiled).execute()

    assert len(compiled.callables) == 2
    assert not execution.failures
    assert execution.datasets["observation", "observations"].sort("id").select(
        "id", "total"
    ).rows() == [(1, 3), (2, 7)]


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
    spec_path = pathlib.Path("_generated/spec/spec.json")
    spec.write_document(spec_definition, spec_path)
    original = spec_path.read_bytes()

    output = render_explorer(spec_definition)

    assert output == pathlib.Path("_generated/explorer/index.html")
    assert spec_path.read_bytes() == original
    assert list(tmp_path.rglob("*.json")) == [tmp_path / spec_path]


def test_build_spec_context() -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    context = spec_render._build_context(spec_definition, False)

    assert (
        context.configuration["entities"]["pump_telemetry"]["datasets"][0]["id"]
        == "pump_telemetry_dataset"
    )
    assert (
        context.configuration["dimensions"]["plant"]["description"]
        == "Manufacturing plant identifier"
    )
    assert context.summary.entity_count == 2
    assert context.summary.dataset_count == 2
    assert sorted(context.summary.function_buckets) == [
        "collapse",
        "conform",
        "expand",
        "read",
        "vectorize",
        "write",
    ]
    assert context.summary.function_buckets == {
        operation: sum(
            function.operation == operation for function in spec_definition.functions.root.values()
        )
        for operation in ("read", "write", "vectorize", "collapse", "expand", "conform")
    }
    assert context.feature_dependencies
    assert context.generated_at is None


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
    assert "examples.pump_analytics.functions.calculation:maximum" in document
    assert "examples/pump_analytics/functions/calculation.py" in document
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
