import json
from pathlib import Path

from uptimely.docs.docs import Documentation
from uptimely.spec import Specification

SPEC_PATH = Path("examples/example_1/generated/spec/spec.json")


def test_generate_json_docs(tmp_path: Path, monkeypatch) -> None:
    specification = Specification.from_json(SPEC_PATH)
    monkeypatch.setattr("uptimely.docs.docs.OUTPUT_DIR", tmp_path / "generated")

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
    monkeypatch.setattr("uptimely.docs.docs.OUTPUT_DIR", tmp_path / "generated")

    document_path = Documentation(specification).create_html()
    document = document_path.read_text(encoding="utf-8")

    assert document_path.name == "docs.html"
    assert not document_path.with_suffix(".json").exists()
    assert 'href="#overview"' in document
    assert 'href="#entities"' in document
    assert 'href="#dimensions"' in document
    assert 'href="#functions"' in document
    assert ">Features<" in document
    assert "Datasets" in document
    assert "Fragments" in document
    assert ">source<" in document
    assert "lg:grid-cols-1" in document
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
    assert "?storage.telemetry_source.path" in document
    assert "$features.operating_point_recommendation" in document
    assert document.index("Pump telemetry") < document.index(
        "rounded-2xl border border-slate-800 bg-slate-900/70 p-6"
    )
    assert "src/features/pump_telemetry/discharge_pressure/main.py:main" not in document
    assert "entrypoint not specified" not in document
    assert "pump" in document
    assert "Documentation" in document
    assert 'id="model"' not in document
    assert "3D Model" not in document
    assert ">source<" in document
    assert "mt-5 border-t border-slate-800 pt-4" in document
    assert document.count(">Vectorize<") == 1
    assert document.count(">Read<") == 1
    assert document.count(">Write<") == 1


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

    first_path = Documentation(specification).create_html(
        output_path=tmp_path / "first" / "docs.html",
    )
    second_path = Documentation(specification).create_html(
        output_path=tmp_path / "second" / "docs.html",
    )

    assert first_path.read_bytes() == second_path.read_bytes()
    assert "generated_at" not in first_path.read_text(encoding="utf-8")
