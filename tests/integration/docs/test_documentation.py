import ast
import json
import pathlib
import re

import pytest

from uptimely import compile, engine, spec
from uptimely.docs import docs

SPEC_PATH = pathlib.Path("examples/example_1/_generated/spec/spec.json")
REFERENCE_PATH = pathlib.Path("docs/specification/specification.md")


@pytest.mark.parametrize(
    ("language", "snippet"),
    re.findall(r"```(json|python)\n(.*?)\n```", REFERENCE_PATH.read_text(), re.DOTALL),
)
def test_specification_reference_snippet_syntax(language: str, snippet: str) -> None:
    if language == "python":
        ast.parse(snippet)
    else:
        document = "{" + snippet + "}" if snippet.lstrip().startswith('"') else snippet
        json.loads(document)


def test_specification_reference_example_parses_compiles_and_executes(
    tmp_path: pathlib.Path,
) -> None:
    reference = REFERENCE_PATH.read_text(encoding="utf-8")
    example_section = reference.split("## Complete JSON Example\n", 1)[1]
    example = example_section.split("```json\n", 1)[1].split("\n```", 1)[0]
    path = tmp_path / "spec.json"
    path.write_text(example, encoding="utf-8")

    specification = spec.Specification.from_json(path)
    compiled = compile.Compiler(specification, features=["total"]).compile()
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
    specification = spec.Specification.from_json(SPEC_PATH)
    monkeypatch.chdir(tmp_path)
    documentation = docs.Documentation(specification)

    document_path = (
        documentation.create_json() if output_format == "json" else documentation.create_html()
    )

    expected = (
        pathlib.Path("_generated/docs/docs.json")
        if output_format == "json"
        else pathlib.Path("_generated/docs/index.html")
    )
    assert document_path == expected
    assert document_path.is_file()
    assert not pathlib.Path("generated").exists()


def test_generate_json_docs(tmp_path: pathlib.Path, monkeypatch) -> None:
    specification = spec.Specification.from_json(SPEC_PATH)
    monkeypatch.setattr("uptimely.docs.docs.OUTPUT_DIR", tmp_path / "_generated")

    data_path = docs.Documentation(specification).create_json()
    data = json.loads(data_path.read_text(encoding="utf-8"))

    assert data_path.name == "docs.json"
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


def test_generate_html_docs(tmp_path: pathlib.Path, monkeypatch) -> None:
    specification = spec.Specification.from_json(SPEC_PATH)
    monkeypatch.setattr("uptimely.docs.docs.OUTPUT_DIR", tmp_path / "_generated" / "docs")

    document_path = docs.Documentation(specification).create_html()
    pages = {
        filename: (document_path.parent / filename).read_text(encoding="utf-8")
        for filename in (
            "spec.html",
            "spec_features.html",
            "spec_datasets.html",
            "spec_dimensions.html",
            "spec_functions.html",
        )
    }
    document = "\n".join(pages.values())

    assert document_path.name == "index.html"
    assert not document_path.with_suffix(".json").exists()
    for filename in pages:
        assert f'href="{filename}"' in document
    assert ">Features<" in document
    assert "Datasets" in document
    assert "Mappings" in document
    assert ">source<" in document
    assert "space-y-5" in document
    for filename, section in (
        ("spec.html", "overview"),
        ("spec_features.html", "entities"),
        ("spec_dimensions.html", "dimensions"),
        ("spec_functions.html", "functions"),
    ):
        assert f'id="{section}"' in pages[filename]
    assert "Pump telemetry" in document
    assert "pump_telemetry_dataset" in document
    assert "Manufacturing plant identifier" in document
    assert "discharge_pressure" in document
    assert "maximum" in document
    assert "normalize_health_signal" in document
    assert "examples.example_1.functions.calculation:maximum" in document
    assert "examples/example_1/functions/calculation.py" in document
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


def test_generate_json_docs_from_in_memory_spec_is_deterministic(tmp_path: pathlib.Path) -> None:
    specification = spec.Specification.from_json(SPEC_PATH)
    specification.path = None

    first_path = docs.Documentation(specification).create_json(
        output_path=tmp_path / "first" / "docs.json",
    )
    second_path = docs.Documentation(specification).create_json(
        output_path=tmp_path / "second" / "docs.json",
    )

    assert first_path.read_bytes() == second_path.read_bytes()


def test_generate_html_docs_from_in_memory_spec_is_deterministic(tmp_path: pathlib.Path) -> None:
    specification = spec.Specification.from_json(SPEC_PATH)
    specification.path = None

    first_path = docs.Documentation(specification).create_html(
        output_path=tmp_path / "first" / "index.html",
    )
    second_path = docs.Documentation(specification).create_html(
        output_path=tmp_path / "second" / "index.html",
    )

    for first_page in first_path.parent.glob("*.html"):
        assert first_page.read_bytes() == (second_path.parent / first_page.name).read_bytes()
        assert "generated_at" not in first_page.read_text(encoding="utf-8")
