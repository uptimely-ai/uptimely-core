import json
import re
from collections import Counter
from functools import wraps
from html.parser import HTMLParser
from pathlib import Path

import pytest

from uptimely.analytics import FeatureGraph
from uptimely.compile import Compiler
from uptimely.docs.docs import Documentation, create_html
from uptimely.plan.models import ExecutionPlan, Plan
from uptimely.spec import Specification

SPEC_PATH = Path("examples/example_1/_generated/spec/spec.json")
REPORTS = {
    "spec.html": "spec",
    "spec_features.html": "features",
    "spec_entities.html": "entities",
    "spec_datasets.html": "datasets",
    "spec_dimensions.html": "dimensions",
    "spec_functions.html": "functions",
    "feature_graph_2d.html": "graph",
    "feature_graph_3d.html": "graph",
    "execution_plan.html": "plan",
    "execution_plan_graph_2d.html": "plan",
    "execution_plan_graph_3d.html": "plan",
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
    features = (index.parent / "spec_features.html").read_text(encoding="utf-8")
    assert "Entity:" in features
    assert "Dataset name" in features
    assert features.index("Dataset name:") < features.index(
        '<article class="rounded-xl border border-slate-800 border-l-4'
    )
    assert "bearing_temperature" in features
    assert "read · read_pump_telemetry" in features
    assert "vectorize · health_signal_normalized" in features
    assert "Row context:" not in features
    entities = (index.parent / "spec_entities.html").read_text(encoding="utf-8")
    assert "pump_telemetry" in entities
    assert "Pump telemetry" in entities
    datasets = (index.parent / "spec_datasets.html").read_text(encoding="utf-8")
    assert "One row per pump and timestamp" in datasets
    assert "read · read_pump_telemetry" in datasets
    assert "Pump analytics" in (index.parent / "spec.html").read_text(encoding="utf-8")
    graph_2d = (index.parent / "feature_graph_2d.html").read_text(encoding="utf-8")
    assert '"label": "health_signal_normalized"' in graph_2d
    assert "force-graph@1.52.0/dist/force-graph.min.js" in graph_2d
    assert ".height(graphContainer.clientHeight)" in graph_2d
    graph_3d = (index.parent / "feature_graph_3d.html").read_text(encoding="utf-8")
    assert '"label": "health_signal_normalized"' in graph_3d
    assert "3d-force-graph" in graph_3d
    for filename in ("feature_graph_2d.html", "feature_graph_3d.html"):
        graph_page = (index.parent / filename).read_text(encoding="utf-8")
        assert 'aria-label="Feature graph views"' in graph_page
        assert 'href="feature_graph_2d.html"' in graph_page
        assert 'href="feature_graph_3d.html"' in graph_page
    for document, filename in (
        (graph_2d, "feature_graph_2d.html"),
        (graph_3d, "feature_graph_3d.html"),
    ):
        assert re.search(
            rf'href="{filename}" aria-current="page"><i class="nav-icon" '
            r'data-lucide="git-fork"',
            document,
        )
    assert ".onEngineStop(" in graph_2d
    assert "graph.zoomToFit(0, Math.max(140, layout.laneLabelWidth + 24))" in graph_2d
    plan = (index.parent / "execution_plan_graph_3d.html").read_text(encoding="utf-8")
    assert 'id="callable-graph"' in plan
    assert "normalize_health_signal" in plan
    assert not Path("_generated/spec").exists()
    assert not Path("_generated/compile").exists()


@pytest.mark.parametrize(
    ("filename", "section_id", "title"),
    [
        ("spec.html", "overview", "Overview"),
        ("spec_features.html", "entities", "Features"),
        ("spec_entities.html", "entities", "Entities"),
        ("spec_datasets.html", "datasets", "Datasets"),
        ("spec_dimensions.html", "dimensions", "Dimensions"),
        ("spec_functions.html", "functions", "Functions"),
    ],
)
def test_specification_pages_render_only_their_section(
    tmp_path: Path, filename: str, section_id: str, title: str
) -> None:
    specification = Specification.from_json(SPEC_PATH)
    Documentation(specification).create_html(tmp_path / "index.html")
    document = (tmp_path / filename).read_text(encoding="utf-8")

    for candidate in ("overview", "entities", "datasets", "dimensions", "functions"):
        assert (f'<section id="{candidate}"' in document) == (candidate == section_id)
    assert 'aria-label="Specification sections"' in document
    assert 'aria-label="Documentation sections"' not in document
    headings = re.findall(r'<h1 class="([^"]+)">([^<]+)</h1>', document)
    assert len(headings) == 1
    assert headings[0][0] == "font-display text-3xl font-semibold tracking-tight text-white"
    assert headings[0][1] == title
    assert "sm:text-6xl" not in document


def test_specification_overview_displays_source_profile(tmp_path: Path) -> None:
    specification = Specification.from_json(SPEC_PATH)
    Documentation(specification).create_html(tmp_path / "index.html")
    document = (tmp_path / "spec.html").read_text(encoding="utf-8")

    assert "Pump analytics" in document
    assert 'data-source-name="python_api" data-generated="true"' in document
    assert ">Source</p>" in document
    assert ">python_api</p>" in document
    assert ">Generated</p>" in document
    assert ">true</span>" in document
    assert "Framework-generated" in document
    assert "rounded-3xl border border-cyan-900/60 bg-gradient-to-br" in document


def test_website_supports_custom_index_path_and_in_memory_spec(tmp_path: Path) -> None:
    specification = Specification.from_json(SPEC_PATH)
    specification.path = None

    index = create_html(specification, tmp_path / "nested" / "analytics.htm")

    assert index == tmp_path / "nested" / "analytics.html"
    assert index.is_file()
    assert all((index.parent / filename).is_file() for filename in REPORTS)


@pytest.mark.parametrize(
    ("filename", "title"),
    [
        ("execution_plan.html", "Overview"),
        ("execution_plan_graph_2d.html", "2D graph"),
        ("execution_plan_graph_3d.html", "3D graph"),
        ("execution_plan_stages.html", "Stages"),
    ],
)
def test_execution_plan_pages_render_only_their_section(
    tmp_path: Path, filename: str, title: str
) -> None:
    specification = Specification.from_json(SPEC_PATH)
    Documentation(specification).create_html(tmp_path / "index.html")
    document = (tmp_path / filename).read_text(encoding="utf-8")

    assert 'aria-label="Execution plan sections"' in document
    is_graph = title in ("2D graph", "3D graph")
    assert re.findall(r'<h1 class="[^"]+">([^<]+)</h1>', document) == ([] if is_graph else [title])
    if is_graph:
        assert 'class="absolute inset-0"' in document
        assert "<header" not in document
        assert ">Callable graph</h2>" not in document
        assert ".linkDirectionalParticles(2)" in document
        assert ".linkDirectionalArrow" not in document
        assert (
            'class="details details-2d"' if title == "2D graph" else 'class="details"'
        ) in document
        if title == "2D graph":
            assert "callableGraph.zoomToFit(0, 140)" in document
            assert ".onEngineStop(" in document
            expected_label = (
                'read_pump_telemetry(source="?storage.telemetry_source.path", '
                'environment="development")'
            )
            assert json.dumps(expected_label) in document
            expected_lines = [
                "read_pump_telemetry(",
                '  source="?storage.telemetry_source.path",',
                '  environment="development"',
                ")",
            ]
            assert f'"label_lines": {json.dumps(expected_lines)}' in document
            expected_list_lines = [
                "optimize_pump_operating_point(",
                "  optimization_features=[",
                '    "discharge_pressure",',
                '    "flow_rate",',
                '    "motor_power",',
                '    "bearing_temperature",',
                '    "vibration_rms"',
                "  ]",
                ")",
            ]
            assert f'"label_lines": {json.dumps(expected_list_lines)}' in document
            expected_object_lines = [
                "maximum(",
                '  feature="bearing_temperature"',
                ")",
            ]
            assert f'"label_lines": {json.dumps(expected_object_lines)}' in document
            assert ".nodeLabel(node => node.label)" in document
            assert "node.label_lines.forEach((line, index) =>" in document
            assert "const rank = node.stage - 1" in document
            graph_data_match = re.search(
                r"const callableGraphData = (.*?);\n\t\tconst callableGraphContainer",
                document,
                re.DOTALL,
            )
            assert graph_data_match is not None
            graph_nodes = json.loads(graph_data_match.group(1))["nodes"]
            normalize_node = next(
                node for node in graph_nodes if node["function_id"] == "normalize_health_signal"
            )
            assert normalize_node["stage"] == 3
            assert "Stage ${stage + 1}" in document
            assert ".onRenderFramePre(drawStageLanes)" in document
            assert "ctx.fillRect(left, -laneHeight / 2, 360, laneHeight)" in document
    assert ('id="plan-overview"' in document) == (title == "Overview")
    assert ('id="callable-graph"' in document) == (title in ("2D graph", "3D graph"))
    assert ("const callableGraphData" in document) == (title in ("2D graph", "3D graph"))
    assert ('id="operations"' in document) == (title == "Stages")
    assert (">Argument</th>" in document) == (title == "Stages")
    if title == "Stages":
        assert "Source dataset:" not in document
        assert "Group by target entity dimensions:" not in document
        assert "bearing_temperature_max" in document
    assert ("3d-force-graph.min.js" in document) == (title == "3D graph")
    assert ("force-graph@1.52.0" in document) == (title == "2D graph")


def test_website_without_timestamp_is_deterministic(tmp_path: Path) -> None:
    specification = Specification.from_json(SPEC_PATH)
    first = Documentation(specification).create_html(tmp_path / "first" / "index.html")
    second = Documentation(specification).create_html(tmp_path / "second" / "index.html")

    for filename in ("index.html", *REPORTS):
        assert (first.parent / filename).read_bytes() == (second.parent / filename).read_bytes()


def test_execution_plan_overview_statistics_match_plan(tmp_path: Path) -> None:
    plan = Compiler(Specification.from_json(SPEC_PATH)).compile()
    plan.export_html(tmp_path / "execution_plan.html", include_navigation=True)
    document = (tmp_path / "execution_plan.html").read_text(encoding="utf-8")
    cards = dict(re.findall(r'data-stat="([^"]+)"[\s\S]*?data-value="(\d+)"', document))
    assert cards == {
        "Callables": str(len(plan.operations)),
        "Functions": str(len({operation.function_id for operation in plan.operations})),
        "Entities": str(len({operation.entity_id for operation in plan.operations})),
        "Features": str(
            len(
                {
                    operation.output
                    for operation in plan.operations
                    if operation.kind == "vectorize" and operation.output is not None
                }
            )
        ),
        "Stages": str(len(plan.execution_stages)),
        "Dependencies": str(sum(len(operation.dependency_ids) for operation in plan.operations)),
        "Max parallel operations": str(max(map(len, plan.execution_stages), default=0)),
    }
    assert dict(re.findall(r'data-operation="([^"]+)" data-count="(\d+)"', document)) == {
        kind: str(count) for kind, count in Counter(op.kind for op in plan.operations).items()
    }
    assert re.findall(r'data-stage="(\d+)" data-count="(\d+)"', document) == [
        (str(index), str(len(stage))) for index, stage in enumerate(plan.execution_stages, start=1)
    ]


def test_empty_execution_plan_overview_statistics(tmp_path: Path) -> None:
    plan = ExecutionPlan(Plan("1.0.0", None, "polars", {}, [], []))
    path = plan.export_html(tmp_path / "execution_plan.html", include_navigation=True)
    document = path.read_text(encoding="utf-8")

    assert re.findall(r'data-value="(\d+)"', document) == ["0"] * 7
    assert "No callable operations." in document
    assert "No execution stages." in document


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
    [
        ("feature_graph_2d.html", "data"),
        ("feature_graph_3d.html", "data"),
        ("execution_plan_graph_2d.html", "callableGraphData"),
        ("execution_plan_graph_3d.html", "callableGraphData"),
    ],
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


def test_execution_plan_graphs_match_compiled_callable_dependencies(tmp_path: Path) -> None:
    specification = Specification.from_json(SPEC_PATH)
    plan = Compiler(specification).compile()
    Documentation(specification).create_html(tmp_path / "index.html")
    payloads = []
    for dimension in ("2d", "3d"):
        document = (tmp_path / f"execution_plan_graph_{dimension}.html").read_text(encoding="utf-8")
        match = re.search(r"const callableGraphData = (.+);", document)
        assert match is not None
        payloads.append(json.loads(match.group(1)))

    assert payloads[0] == payloads[1]
    assert {node["id"] for node in payloads[0]["nodes"]} == {
        operation.id for operation in plan.operations
    }
    assert all(node["node_type"] == "callable" for node in payloads[0]["nodes"])
    assert {(link["source"], link["target"]) for link in payloads[0]["links"]} == {
        (dependency_id, operation.id)
        for operation in plan.operations
        for dependency_id in operation.dependency_ids
    }


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
