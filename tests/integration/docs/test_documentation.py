import json
from pathlib import Path

import pytest

from uptimely.docs.docs import Documentation
from uptimely.spec import Specification

SPEC_PATH = Path("examples/example_1/_generated/spec/spec.json")


@pytest.mark.parametrize("output_format", ["json", "html"])
def test_reference_exports_to_default_directory(
    tmp_path: Path, monkeypatch, output_format: str
) -> None:
    specification = Specification.from_json(SPEC_PATH)
    monkeypatch.chdir(tmp_path)
    documentation = Documentation(specification)

    document_path = (
        documentation.create_json() if output_format == "json" else specification.create_html()
    )

    expected = (
        Path("_generated/docs/docs.json")
        if output_format == "json"
        else Path("_generated/spec/spec.html")
    )
    assert document_path == expected
    assert document_path.is_file()
    assert not Path("generated").exists()


def test_generate_json_docs(tmp_path: Path, monkeypatch) -> None:
    specification = Specification.from_json(SPEC_PATH)
    monkeypatch.setattr("uptimely.docs.docs.OUTPUT_DIR", tmp_path / "_generated")

    data_path = Documentation(specification).create_json()
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


def test_generate_html_docs(tmp_path: Path, monkeypatch) -> None:
    specification = Specification.from_json(SPEC_PATH)
    monkeypatch.setattr("uptimely.spec.render.OUTPUT_DIR", tmp_path / "_generated" / "spec")

    document_path = specification.create_html()
    document = document_path.read_text(encoding="utf-8")

    assert document_path.name == "spec.html"
    assert not document_path.with_suffix(".json").exists()
    assert 'href="#overview"' in document
    assert 'href="#entities"' in document
    assert 'href="#dimensions"' in document
    assert 'href="#functions"' in document
    assert ">Features<" in document
    assert "Datasets" in document
    assert "Fragments" in document
    assert ">source<" in document
    assert "space-y-5" in document
    assert 'href="#engines"' not in document
    assert 'href="#graph"' not in document
    assert 'href="#variables"' not in document
    assert 'href="#connections"' not in document
    assert 'href="#orchestration"' not in document
    assert 'href="#environments"' not in document
    assert document.index('id="overview"') < document.index('id="entities"')
    assert document.index('id="entities"') < document.index('id="dimensions"')
    assert document.index('id="dimensions"') < document.index('id="functions"')
    assert 'id="engines"' not in document
    assert 'id="graph"' not in document
    assert 'id="variables"' not in document
    assert 'id="connections"' not in document
    assert 'id="orchestration"' not in document
    assert 'id="environments"' not in document
    assert "Pump telemetry" in document
    assert "pump_telemetry_dataset" in document
    assert "Manufacturing plant identifier" in document
    assert "discharge_pressure" in document
    assert "aggregate_by_dimension" in document
    assert "normalize_health_signal" in document
    assert "examples.example_1.functions.calculation:aggregate_by_dimension" in document
    assert "examples/example_1/functions/calculation.py" in document
    assert "file:///" in document
    assert "-&gt; LazyFrame" in document
    assert "-&gt; Expr" in document
    assert "read · read_pump_telemetry" in document
    assert document.index("Pump telemetry") < document.index(
        "rounded-2xl border border-slate-800 bg-slate-900/70 p-6"
    )
    assert "src/features/pump_telemetry/discharge_pressure/main.py:main" not in document
    assert "entrypoint not specified" not in document
    assert "pump" in document
    assert ">Specification<" in document
    assert 'id="model"' not in document
    assert "3D Model" not in document
    assert ">source<" in document
    assert "mt-5 border-t border-slate-800 pt-4" in document
    for group_name in ("vectorize", "read", "write"):
        assert f'data-function-group="{group_name}"' in document
    assert "Vectorize" in document
    assert "Read" in document
    assert "Write" in document


def test_generate_json_docs_from_in_memory_spec_is_deterministic(tmp_path: Path) -> None:
    specification = Specification.from_json(SPEC_PATH)
    specification.path = None

    first_path = Documentation(specification).create_json(
        output_path=tmp_path / "first" / "docs.json",
    )
    second_path = Documentation(specification).create_json(
        output_path=tmp_path / "second" / "docs.json",
    )

    assert first_path.read_bytes() == second_path.read_bytes()


def test_generate_html_docs_from_in_memory_spec_is_deterministic(tmp_path: Path) -> None:
    specification = Specification.from_json(SPEC_PATH)
    specification.path = None

    first_path = specification.create_html(
        output_path=tmp_path / "first" / "spec.html",
    )
    second_path = specification.create_html(
        output_path=tmp_path / "second" / "spec.html",
    )

    assert first_path.read_bytes() == second_path.read_bytes()
    assert "generated_at" not in first_path.read_text(encoding="utf-8")
