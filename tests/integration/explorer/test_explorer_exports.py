"""Tests for Explorer exports."""

import ast
import json
import pathlib
import re

import pytest

from uptimely import analytics, compile, engine
from uptimely.explorer import explorer

ANALYTICS_PATH = pathlib.Path("examples/pump_analytics/_generated/analytics/analytics.json")
REFERENCE_PATH = pathlib.Path("docs/specification/analytics.md")


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


def test_analytics_reference_example_parses_compiles_and_executes(
    tmp_path: pathlib.Path,
) -> None:
    reference = REFERENCE_PATH.read_text(encoding="utf-8")
    example_section = reference.split("## Complete JSON Example\n", 1)[1]
    example = example_section.split("```json\n", 1)[1].split("\n```", 1)[0]
    path = tmp_path / "analytics.json"
    path.write_text(example, encoding="utf-8")

    analytics_definition = analytics.Analytics(json=path)
    compiled = compile.Compiler(analytics_definition, features=["total"]).compile()
    execution = engine.Engine(compiled).execute()

    assert len(compiled.operations) == 2
    assert not execution.failures
    assert execution.datasets["observation", "observations"].sort("id").select(
        "id", "total"
    ).rows() == [(1, 3), (2, 7)]


@pytest.mark.parametrize("output_format", ["json", "html"])
def test_reference_exports_to_default_directory(
    tmp_path: pathlib.Path, monkeypatch, output_format: str
) -> None:
    analytics_definition = analytics.Analytics(json=ANALYTICS_PATH)
    monkeypatch.chdir(tmp_path)
    explorer_instance = explorer.Explorer(analytics_definition)

    document_path = (
        explorer_instance.create_json()
        if output_format == "json"
        else explorer_instance.create_html()
    )

    expected = (
        pathlib.Path("_generated/explorer/explorer.json")
        if output_format == "json"
        else pathlib.Path("_generated/explorer/index.html")
    )
    assert document_path == expected
    assert document_path.is_file()
    assert not pathlib.Path("generated").exists()


def test_generate_json_reference(tmp_path: pathlib.Path, monkeypatch) -> None:
    analytics_definition = analytics.Analytics(json=ANALYTICS_PATH)
    monkeypatch.setattr("uptimely.explorer.explorer.EXPLORER_OUTPUT_DIR", tmp_path / "_generated")

    data_path = explorer.Explorer(analytics_definition).create_json()
    data = json.loads(data_path.read_text(encoding="utf-8"))

    assert data_path.name == "explorer.json"
    assert (
        data["configuration"]["entities"]["pump_telemetry"]["datasets"][0]["id"]
        == "pump_telemetry_dataset"
    )
    assert (
        data["configuration"]["dimensions"]["plant"]["description"]
        == "Manufacturing plant identifier"
    )
    assert data["summary"]["entity_count"] == 2
    assert data["summary"]["dataset_count"] == 2
    assert data["feature_dependencies"]
    assert data["generated_at"] is None
    assert not data_path.with_suffix(".html").exists()


def test_generate_html_explorer(tmp_path: pathlib.Path, monkeypatch) -> None:
    analytics_definition = analytics.Analytics(json=ANALYTICS_PATH)
    monkeypatch.setattr(
        "uptimely.explorer.explorer.EXPLORER_OUTPUT_DIR", tmp_path / "_generated" / "explorer"
    )

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


def test_generate_json_reference_from_in_memory_analytics_is_deterministic(
    tmp_path: pathlib.Path,
) -> None:
    analytics_definition = analytics.Analytics(json=ANALYTICS_PATH)
    analytics_definition.path = None

    first_path = explorer.Explorer(analytics_definition).create_json(
        output_path=tmp_path / "first" / "explorer.json",
    )
    second_path = explorer.Explorer(analytics_definition).create_json(
        output_path=tmp_path / "second" / "explorer.json",
    )

    assert first_path.read_bytes() == second_path.read_bytes()


def test_generate_html_explorer_from_in_memory_analytics_is_deterministic(
    tmp_path: pathlib.Path,
) -> None:
    analytics_definition = analytics.Analytics(json=ANALYTICS_PATH)
    analytics_definition.path = None

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
