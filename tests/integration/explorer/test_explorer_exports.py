"""Tests for Explorer exports."""

import ast
import json
import pathlib
import re

import pytest

from uptimely import analytics, compiler, engine
from uptimely.explorer import analytics_render, explorer

ANALYTICS_PATH = pathlib.Path("examples/pump_analytics/_generated/analytics/analytics.json")
REFERENCE_PATH = pathlib.Path("docs/specification/analytics.md")
OBSERVATION_TOTALS_PATH = pathlib.Path("tests/fixtures/analytics/observation_totals.json")


@pytest.mark.parametrize(
    ("language", "snippet"),
    re.findall(r"```(json|python)\n(.*?)\n```", REFERENCE_PATH.read_text(), re.DOTALL),
)
def test_analytics_reference_snippet_syntax(language: str, snippet: str) -> None:
    if language == "python":
        ast.parse(snippet)
    else:
        document = "{" + snippet + "}" if snippet.lstrip().startswith('"') else snippet
        json.loads(document)


def test_analytics_json_parses_compiles_and_executes() -> None:
    analytics_definition = analytics.load_analytics(OBSERVATION_TOTALS_PATH)
    compiled = compiler.Compiler(analytics_definition, features=["total"]).compile()
    execution = engine.Engine(compiled).execute()

    assert len(compiled.callables) == 2
    assert not execution.failures
    assert execution.datasets["observation", "observations"].sort("id").select(
        "id", "total"
    ).rows() == [(1, 3), (2, 7)]


def test_reference_exports_to_default_directory(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    analytics_definition = analytics.load_analytics(ANALYTICS_PATH)
    monkeypatch.chdir(tmp_path)
    explorer_instance = explorer.Explorer(analytics_definition)

    document_path = explorer_instance.create_html()
    expected = pathlib.Path("_generated/explorer/index.html")
    assert document_path == expected
    assert document_path.is_file()
    assert not pathlib.Path("generated").exists()
    assert not list(tmp_path.rglob("*.json"))


def test_html_export_preserves_analytics_definition(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    analytics_definition = analytics.load_analytics(ANALYTICS_PATH)
    monkeypatch.chdir(tmp_path)
    analytics_path = pathlib.Path("_generated/analytics/analytics.json")
    analytics.write_document(analytics_definition, analytics_path)
    original = analytics_path.read_bytes()

    output = explorer.Explorer(analytics_definition).create_html()

    assert output == pathlib.Path("_generated/explorer/index.html")
    assert analytics_path.read_bytes() == original
    assert list(tmp_path.rglob("*.json")) == [tmp_path / analytics_path]


def test_build_analytics_context() -> None:
    analytics_definition = analytics.load_analytics(ANALYTICS_PATH)
    context = analytics_render._build_context(analytics_definition, False)

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
            function.operation == operation
            for function in analytics_definition.functions.root.values()
        )
        for operation in ("read", "write", "vectorize", "collapse", "expand", "conform")
    }
    assert context.feature_dependencies
    assert context.generated_at is None


def test_generate_html_explorer(tmp_path: pathlib.Path, monkeypatch) -> None:
    analytics_definition = analytics.load_analytics(ANALYTICS_PATH)
    monkeypatch.chdir(tmp_path)

    document_path = explorer.Explorer(analytics_definition).create_html()
    pages = {
        filename: (document_path.parent / filename).read_text(encoding="utf-8")
        for filename in (
            "analytics/overview.html",
            "analytics/features.html",
            "analytics/datasets.html",
            "analytics/dimensions.html",
            "analytics/functions.html",
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
        ("analytics/overview.html", "overview"),
        ("analytics/features.html", "entities"),
        ("analytics/dimensions.html", "dimensions"),
        ("analytics/functions.html", "functions"),
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


def test_generate_html_explorer_from_in_memory_analytics_is_deterministic(
    tmp_path: pathlib.Path,
) -> None:
    analytics_definition = analytics.load_analytics(ANALYTICS_PATH)

    first_path = explorer.Explorer(analytics_definition).create_html(
        output_path=tmp_path / "first" / "index.html",
    )
    second_path = explorer.Explorer(analytics_definition).create_html(
        output_path=tmp_path / "second" / "index.html",
    )

    for first_page in first_path.parent.rglob("*.html"):
        relative_path = first_page.relative_to(first_path.parent)
        assert first_page.read_bytes() == (second_path.parent / relative_path).read_bytes()
        assert "generated_at" not in first_page.read_text(encoding="utf-8")
