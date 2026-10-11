import json
import re
from functools import wraps
from html.parser import HTMLParser
from pathlib import Path

import pytest

from uptimely.analytics import FeatureGraph
from uptimely.compile import Compiler
from uptimely.docs.docs import Documentation, create_html
from uptimely.spec import Specification

SPEC_PATH = Path("examples/example_1/_generated/spec/spec.json")
REPORTS = {
    "spec.html": "spec",
    "spec_features.html": "features",
    "spec_dimensions.html": "dimensions",
    "spec_functions.html": "functions",
    "feature_graph.html": "graph",
    "execution_plan.html": "plan",
    "execution_plan_stages.html": "stages",
}


class NavigationCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_navigation = False
        self.links: list[str] = []
        self.active_links: list[str] = []
        self.html_count = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "html":
            self.html_count += 1
        if tag == "nav" and attributes.get("aria-label") == "Documentation pages":
            self.in_navigation = True
        if tag == "a" and self.in_navigation:
            href = attributes["href"]
            assert href is not None
            self.links.append(href)
            if attributes.get("aria-current") == "page":
                self.active_links.append(href)

    def handle_endtag(self, tag: str) -> None:
        if tag == "nav":
            self.in_navigation = False


def test_website_exports_all_reports_with_relative_navigation(tmp_path: Path, monkeypatch) -> None:
    specification = Specification.from_json(SPEC_PATH)
    monkeypatch.chdir(tmp_path)

    index = Documentation(specification).create_html()

    assert index == Path("_generated/docs/index.html")
    assert {path.name for path in index.parent.iterdir()} == {"index.html", *REPORTS}
    for filename in ("index.html", *REPORTS):
        parser = NavigationCollector()
        document = (index.parent / filename).read_text(encoding="utf-8")
        parser.feed(document)
        assert parser.html_count == 1
        assert set(parser.links) == set(REPORTS)
        for href in parser.links:
            assert (index.parent / href).is_file()
        assert parser.active_links == ([] if filename == "index.html" else [filename])
        assert "<iframe" not in document
    assert "Pump telemetry" in (index.parent / "spec_features.html").read_text(encoding="utf-8")
    graph = (index.parent / "feature_graph.html").read_text(encoding="utf-8")
    assert '"label": "health_signal_normalized"' in graph
    assert ".height(graphContainer.clientHeight)" in graph
    plan = (index.parent / "execution_plan.html").read_text(encoding="utf-8")
    assert "Callable graph" in plan
    assert "normalize_health_signal" in plan
    assert not Path("_generated/spec").exists()
    assert not Path("_generated/compile").exists()


@pytest.mark.parametrize(
    ("filename", "section_id"),
    [
        ("spec.html", "overview"),
        ("spec_features.html", "entities"),
        ("spec_dimensions.html", "dimensions"),
        ("spec_functions.html", "functions"),
    ],
)
def test_specification_pages_render_only_their_section(
    tmp_path: Path, filename: str, section_id: str
) -> None:
    specification = Specification.from_json(SPEC_PATH)
    Documentation(specification).create_html(tmp_path / "index.html")
    document = (tmp_path / filename).read_text(encoding="utf-8")

    for candidate in ("overview", "entities", "dimensions", "functions"):
        assert (f'<section id="{candidate}"' in document) == (candidate == section_id)
    assert 'aria-label="Specification sections"' in document
    assert 'aria-label="Documentation sections"' not in document
    headings = re.findall(r'<h1 class="([^"]+)">([^<]+)</h1>', document)
    assert len(headings) == 1
    assert headings[0][0] == "font-display text-3xl font-semibold tracking-tight text-white"
    assert (
        headings[0][1]
        == {
            "overview": "Overview",
            "entities": "Features",
            "dimensions": "Dimensions",
            "functions": "Functions",
        }[section_id]
    )
    assert "sm:text-6xl" not in document


def test_website_supports_custom_index_path_and_in_memory_spec(tmp_path: Path) -> None:
    specification = Specification.from_json(SPEC_PATH)
    specification.path = None

    index = create_html(specification, tmp_path / "nested" / "analytics.htm")

    assert index == tmp_path / "nested" / "analytics.html"
    assert index.is_file()
    assert all((index.parent / filename).is_file() for filename in REPORTS)


@pytest.mark.parametrize(
    ("filename", "title"),
    [("execution_plan.html", "Overview"), ("execution_plan_stages.html", "Stages")],
)
def test_execution_plan_pages_render_only_their_section(
    tmp_path: Path, filename: str, title: str
) -> None:
    specification = Specification.from_json(SPEC_PATH)
    Documentation(specification).create_html(tmp_path / "index.html")
    document = (tmp_path / filename).read_text(encoding="utf-8")

    assert 'aria-label="Execution plan sections"' in document
    assert re.findall(r'<h1 class="[^"]+">([^<]+)</h1>', document) == [title]
    assert ('id="plan-overview"' in document) == (title == "Overview")
    assert ('id="callable-graph"' in document) == (title == "Overview")
    assert ("const callableGraphData" in document) == (title == "Overview")
    assert ('id="operations"' in document) == (title == "Stages")
    assert (">Argument</th>" in document) == (title == "Stages")
    assert ("3d-force-graph.min.js" in document) == (title == "Overview")


def test_website_without_timestamp_is_deterministic(tmp_path: Path) -> None:
    specification = Specification.from_json(SPEC_PATH)
    first = Documentation(specification).create_html(tmp_path / "first" / "index.html")
    second = Documentation(specification).create_html(tmp_path / "second" / "index.html")

    for filename in ("index.html", *REPORTS):
        assert (first.parent / filename).read_bytes() == (second.parent / filename).read_bytes()


@pytest.mark.parametrize("filename", REPORTS)
def test_website_rejects_index_path_overwriting_report(tmp_path: Path, filename: str) -> None:
    specification = Specification.from_json(SPEC_PATH)

    with pytest.raises(ValueError, match="must not overwrite"):
        Documentation(specification).create_html(tmp_path / filename)

    assert not list(tmp_path.iterdir())


def test_standalone_exports_have_no_website_navigation(tmp_path: Path) -> None:
    specification = Specification.from_json(SPEC_PATH)
    paths = [
        specification.create_html(tmp_path / "spec" / "spec.html"),
        FeatureGraph(specification).export_html(tmp_path / "graph" / "graph.html"),
        Compiler(specification).compile().export_html(tmp_path / "plan" / "plan.html"),
    ]

    for path in paths:
        parser = NavigationCollector()
        parser.feed(path.read_text(encoding="utf-8"))
        assert parser.html_count == 1
        assert not parser.links
    standalone_spec = paths[0].read_text(encoding="utf-8")
    assert len(re.findall(r"<h1\b", standalone_spec)) == 1
    assert all(
        f'<section id="{section}"' in standalone_spec
        for section in ("overview", "entities", "dimensions", "functions")
    )
    standalone_plan = paths[2].read_text(encoding="utf-8")
    assert 'id="plan-overview"' in standalone_plan
    assert 'id="callable-graph"' in standalone_plan
    assert 'id="operations"' in standalone_plan
    assert not (paths[2].parent / "execution_plan_stages.html").exists()


def test_website_propagates_compilation_errors_without_writing_reports(tmp_path: Path) -> None:
    specification = Specification.from_json(SPEC_PATH)
    specification.functions.read[
        "read_pump_telemetry"
    ].entrypoint = "missing_functions:read_pump_telemetry"

    with pytest.raises((ImportError, ValueError), match="missing_functions"):
        Documentation(specification).create_html(tmp_path / "index.html")

    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    ("filename", "variable"),
    [("feature_graph.html", "data"), ("execution_plan.html", "callableGraphData")],
)
def test_website_graph_links_reference_exported_nodes(
    tmp_path: Path, filename: str, variable: str
) -> None:
    specification = Specification.from_json(SPEC_PATH)
    Documentation(specification).create_html(tmp_path / "index.html")
    document = (tmp_path / filename).read_text(encoding="utf-8")
    match = re.search(rf"const {variable} = (.+);", document)
    assert match is not None
    payload = json.loads(match.group(1))
    identifiers = {node["id"] for node in payload["nodes"]}

    assert identifiers
    assert payload["links"]
    assert len(identifiers) == len(payload["nodes"])
    for link in payload["links"]:
        assert link["source"] in identifiers
        assert link["target"] in identifiers


def test_website_does_not_execute_analytics(tmp_path: Path, monkeypatch) -> None:
    from examples.example_1.functions import source

    @wraps(source.read_pump_telemetry)
    def fail_if_executed(*args: object, **kwargs: object) -> None:
        raise AssertionError("Website generation must not execute analytics")

    monkeypatch.setattr(source, "read_pump_telemetry", fail_if_executed)
    specification = Specification.from_json(SPEC_PATH)

    assert Documentation(specification).create_html(tmp_path / "index.html").is_file()


def test_website_can_include_specification_timestamp(tmp_path: Path) -> None:
    specification = Specification.from_json(SPEC_PATH)

    Documentation(specification).create_html(tmp_path / "index.html", include_generated_at=True)

    assert re.search(
        r"generated \d{4}-\d{2}-\d{2}T",
        (tmp_path / "spec.html").read_text(encoding="utf-8"),
    )
