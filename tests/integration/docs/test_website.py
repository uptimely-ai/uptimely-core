import collections
import functools
import json
import pathlib
import re
import threading
from html import parser as html_parser
from http import server as http_server
from urllib import parse as url_parse
from urllib import request

import pytest
from examples.example_1.functions import source

from uptimely import analytics, compile, spec
from uptimely.analytics import render as graph_render
from uptimely.docs import docs
from uptimely.spec import render as spec_render

SPEC_PATH = pathlib.Path("examples/example_1/_generated/spec/spec.json")
REPORTS = {
    "spec/overview.html": "spec",
    "spec/features.html": "features",
    "spec/entities.html": "entities",
    "spec/datasets.html": "datasets",
    "spec/dimensions.html": "dimensions",
    "spec/functions.html": "functions",
    "graph/feature_graph.html": "graph",
    "plan/overview.html": "plan",
    "plan/graph.html": "plan",
    "plan/stages.html": "stages",
}


class NavigationCollector(html_parser.HTMLParser):
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


class IconCollector(html_parser.HTMLParser):
    """Collect decorative icons and heading labels independently of their markup."""

    def __init__(self) -> None:
        super().__init__()
        self.in_heading = False
        self.in_navigation = False
        self.heading_parts: list[str] = []
        self.headings: list[str] = []
        self.heading_icons: list[dict[str, str | None]] = []
        self.navigation_icons: list[dict[str, str | None]] = []
        self.icons: list[dict[str, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "h1":
            self.in_heading = True
            self.heading_parts = []
        if tag == "nav":
            self.in_navigation = True
        if "data-lucide" in attributes:
            self.icons.append(attributes)
            if self.in_heading:
                self.heading_icons.append(attributes)
            if self.in_navigation:
                self.navigation_icons.append(attributes)

    def handle_data(self, data: str) -> None:
        if self.in_heading:
            self.heading_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "h1":
            self.headings.append("".join(self.heading_parts).strip())
            self.in_heading = False
        if tag == "nav":
            self.in_navigation = False


def heading_titles(document: str) -> list[str]:
    """Return visible page titles, ignoring decorative icon markup."""
    collector = IconCollector()
    collector.feed(document)
    return collector.headings


def test_website_icons_share_section_palette(tmp_path: pathlib.Path) -> None:
    docs.create_html(spec.Specification(), tmp_path / "index.html")
    expected = {
        "index.html": ("home", "house", "Untitled analytics project"),
        "spec/overview.html": ("overview", "layout-dashboard", "Overview"),
        "spec/features.html": ("features", "sparkles", "Features"),
        "spec/entities.html": ("entities", "boxes", "Entities"),
        "spec/datasets.html": ("datasets", "table", "Datasets"),
        "spec/dimensions.html": ("dimensions", "layers-3", "Dimensions"),
        "spec/functions.html": ("functions", "braces", "Functions"),
        "graph/feature_graph.html": ("lineage", "git-fork", "Feature lineage"),
        "plan/overview.html": ("execution", "workflow", "Overview"),
        "plan/graph.html": ("execution-graph", "network", "Execution graph"),
        "plan/stages.html": ("stages", "list-ordered", "Stages"),
    }
    palette = {
        "home": "#93c5fd",
        "specification": "#67e8f9",
        "overview": "#93c5fd",
        "features": "#f9a8d4",
        "entities": "#fdba74",
        "datasets": "#6ee7b7",
        "dimensions": "#a5b4fc",
        "functions": "#fcd34d",
        "lineage": "#c4b5fd",
        "execution": "#fcd34d",
        "execution-graph": "#fcd34d",
        "stages": "#fcd34d",
    }
    for filename, (key, symbol, title) in expected.items():
        document = (tmp_path / filename).read_text(encoding="utf-8")
        collector = IconCollector()
        collector.feed(document)
        assert collector.headings == [title]
        assert len(collector.heading_icons) == 1
        heading_icon = collector.heading_icons[0]
        assert heading_icon["data-lucide"] == symbol
        assert f"icon--{key}" in (heading_icon["class"] or "").split()
        assert any(
            item["data-lucide"] == symbol and f"icon--{key}" in (item["class"] or "").split()
            for item in collector.navigation_icons
        )
        assert all(item["aria-hidden"] == "true" for item in collector.icons)
        for icon_key, color in palette.items():
            assert f".icon--{icon_key} {{ --icon-color: {color};" in document
        assert ".site-icon { color: var(--icon-color);" in document
        assert 'a[aria-current="page"]' in document
        assert "a:focus-visible" in document


def test_website_exports_all_reports_with_relative_navigation(
    tmp_path: pathlib.Path, monkeypatch
) -> None:
    specification = spec.Specification.from_json(SPEC_PATH)
    monkeypatch.chdir(tmp_path)

    index = docs.Documentation(specification).create_html()

    assert index == pathlib.Path("_generated/docs/index.html")
    assert {path.name for path in index.parent.iterdir()} == {"index.html", "spec", "graph", "plan"}
    for filename in ("index.html", *REPORTS):
        page_file = index.parent / filename
        parser = NavigationCollector()
        document = page_file.read_text(encoding="utf-8")
        parser.feed(document)
        assert parser.html_count == 1
        assert {(page_file.parent / href).resolve() for href in parser.links} == {
            (index.parent / path).resolve() for path in ("index.html", *REPORTS)
        }
        for href in parser.links:
            assert (page_file.parent / href).is_file()
        assert [(page_file.parent / href).resolve() for href in parser.active_links] == [
            page_file.resolve()
        ]
        assert "<iframe" not in document
    assert "Pump telemetry" in (index.parent / "spec/features.html").read_text(encoding="utf-8")
    features = (index.parent / "spec/features.html").read_text(encoding="utf-8")
    assert "Entity:" in features
    assert "Dataset name" in features
    assert features.index("Dataset name:") < features.index(
        '<article class="rounded-xl border border-slate-800 border-l-4'
    )
    assert "bearing_temperature" in features
    assert "read · read_pump_telemetry" in features
    assert "vectorize · health_signal_normalized" in features
    assert "Row context:" not in features
    entities = (index.parent / "spec/entities.html").read_text(encoding="utf-8")
    assert "pump_telemetry" in entities
    assert "Pump telemetry" in entities
    datasets = (index.parent / "spec/datasets.html").read_text(encoding="utf-8")
    assert "One row per pump and timestamp" in datasets
    assert "read · read_pump_telemetry" in datasets
    assert "Pump analytics" in (index.parent / "spec/overview.html").read_text(encoding="utf-8")
    graph_2d = (index.parent / "graph/feature_graph.html").read_text(encoding="utf-8")
    assert '"label": "health_signal_normalized"' in graph_2d
    assert "force-graph@1.52.0/dist/force-graph.min.js" in graph_2d
    assert ".height(graphContainer.clientHeight)" in graph_2d
    assert "3d-force-graph" in graph_2d
    assert 'aria-label="Feature graph views"' not in graph_2d
    assert re.search(
        r'href="../graph/feature_graph.html" aria-current="page">'
        r'<i class="site-icon icon--lineage nav-icon" '
        r'data-lucide="git-fork"',
        graph_2d,
    )
    assert ".onEngineStop(" in graph_2d
    assert "graph.zoomToFit(0, Math.max(140, layout.laneLabelWidth + 24))" in graph_2d
    plan = (index.parent / "plan/graph.html").read_text(encoding="utf-8")
    assert 'id="callable-graph"' in plan
    assert "normalize_health_signal" in plan
    assert not pathlib.Path("_generated/spec").exists()
    assert not pathlib.Path("_generated/compile").exists()


def test_homepage_shows_project_counts_and_journey(tmp_path: pathlib.Path, monkeypatch) -> None:
    specification = spec.Specification.from_json(SPEC_PATH)
    expected_plan = compile.Compiler(specification).compile()
    compile_calls = 0
    original_compile = compile.Compiler.compile

    @functools.wraps(original_compile)
    def count_compile(self):
        nonlocal compile_calls
        compile_calls += 1
        return original_compile(self)

    monkeypatch.setattr(compile.Compiler, "compile", count_compile)
    index = docs.create_html(specification, tmp_path / "index.html")
    document = index.read_text(encoding="utf-8")

    assert compile_calls == 1
    assert "<title>Pump analytics | OpenAnalytics</title>" in document
    assert heading_titles(document) == ["Pump analytics"]
    datasets = [
        dataset for entity in specification.entities.values() for dataset in entity.datasets
    ]
    assert dict(re.findall(r'data-stat="([^"]+)" data-value="(\d+)"', document)) == {
        "Entities": str(len(specification.entities)),
        "Datasets": str(len(datasets)),
        "Features": str(sum(len(dataset.features) for dataset in datasets)),
        "Functions": str(
            sum(len(group) for group in specification.functions.model_dump().values())
        ),
        "Operations": str(len(expected_plan.operations)),
        "Stages": str(len(expected_plan.execution_stages)),
    }
    assert "Specification 0.1.0" in document
    assert 'aria-label="Project counts"' in document
    assert 'aria-label="Analytics journey"' in document
    assert re.findall(r'<li class="journey-step (\S+) icon--\1">', document) == [
        "specification",
        "lineage",
        "execution",
    ]
    for href, action in (
        ("spec/overview.html", "Explore specification"),
        ("graph/feature_graph.html", "Trace dependencies"),
        ("plan/overview.html", "Inspect the plan"),
    ):
        assert f'<a href="{href}">{action}' in document
        assert (index.parent / href).is_file()
    assert "does not run analytical operations" in document
    assert "prefers-reduced-motion: reduce" in document


@pytest.mark.parametrize("name", [None, "", '<script>alert("title")</script> & Analytics'])
def test_homepage_handles_unnamed_and_escaped_projects(
    tmp_path: pathlib.Path, name: str | None
) -> None:
    index = docs.create_html(spec.Specification(name=name), tmp_path / "index.html")
    document = index.read_text(encoding="utf-8")

    assert re.findall(r'data-value="(\d+)"', document) == ["0"] * 6
    if not name:
        assert heading_titles(document) == ["Untitled analytics project"]
    else:
        assert (
            "<span>&lt;script&gt;alert(&#34;title&#34;)&lt;/script&gt; &amp; Analytics</span>"
            in document
        )
        assert name not in document


@pytest.mark.parametrize(
    ("filename", "section_id", "title"),
    [
        ("spec/overview.html", "overview", "Overview"),
        ("spec/features.html", "entities", "Features"),
        ("spec/entities.html", "entities", "Entities"),
        ("spec/datasets.html", "datasets", "Datasets"),
        ("spec/dimensions.html", "dimensions", "Dimensions"),
        ("spec/functions.html", "functions", "Functions"),
    ],
)
def test_specification_pages_render_only_their_section(
    tmp_path: pathlib.Path, filename: str, section_id: str, title: str
) -> None:
    specification = spec.Specification.from_json(SPEC_PATH)
    docs.Documentation(specification).create_html(tmp_path / "index.html")
    document = (tmp_path / filename).read_text(encoding="utf-8")

    for candidate in ("overview", "entities", "datasets", "dimensions", "functions"):
        assert (f'<section id="{candidate}"' in document) == (candidate == section_id)
    assert 'aria-label="Specification sections"' in document
    assert 'aria-label="Documentation sections"' not in document
    headings = re.findall(r'<h1 class="([^"]+)">.*?<span>([^<]+)</span></h1>', document)
    assert len(headings) == 1
    assert headings[0][0] == (
        "title-with-icon font-display text-3xl font-semibold tracking-tight text-white"
    )
    assert headings[0][1] == title
    assert "sm:text-6xl" not in document


def test_specification_overview_displays_source_profile(tmp_path: pathlib.Path) -> None:
    specification = spec.Specification.from_json(SPEC_PATH)
    docs.Documentation(specification).create_html(tmp_path / "index.html")
    document = (tmp_path / "spec/overview.html").read_text(encoding="utf-8")

    assert "Pump analytics" in document
    assert 'data-source-name="python_api" data-generated="true"' in document
    assert ">Source</p>" in document
    assert ">python_api</p>" in document
    assert ">Generated</p>" in document
    assert ">true</span>" in document
    assert "Framework-generated" in document
    assert "rounded-3xl border border-cyan-900/60 bg-gradient-to-br" in document


def test_website_supports_custom_index_path_and_in_memory_spec(tmp_path: pathlib.Path) -> None:
    specification = spec.Specification.from_json(SPEC_PATH)
    specification.path = None

    index = docs.create_html(specification, tmp_path / "nested" / "analytics.htm")

    assert index == tmp_path / "nested" / "analytics.html"
    assert index.is_file()
    assert all((index.parent / filename).is_file() for filename in REPORTS)
    for filename in (index.name, *REPORTS):
        parser = NavigationCollector()
        page_file = index.parent / filename
        parser.feed(page_file.read_text(encoding="utf-8"))
        assert ("analytics.html" if filename == index.name else "../analytics.html") in parser.links
        assert "index.html" not in parser.links
        assert [(page_file.parent / href).resolve() for href in parser.active_links] == [
            page_file.resolve()
        ]
        assert all((page_file.parent / href).is_file() for href in parser.links)


@pytest.mark.parametrize("index_name", ["index.html", "analytics.html"])
def test_relocated_website_navigation_works_under_url_prefix(
    tmp_path: pathlib.Path, index_name: str
) -> None:
    original = tmp_path / "generated"
    docs.create_html(spec.Specification(), original / index_name)
    host_root = tmp_path / "hosted"
    relocated = host_root / "projects" / "analytics"
    relocated.parent.mkdir(parents=True)
    original.rename(relocated)
    handler = functools.partial(http_server.SimpleHTTPRequestHandler, directory=str(host_root))
    with http_server.ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
        worker = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
        worker.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}/projects/analytics/"
            expected_urls = {url_parse.urljoin(base, page) for page in (index_name, *REPORTS)}
            for page in (index_name, *REPORTS):
                page_url = url_parse.urljoin(base, page)
                with request.urlopen(page_url, timeout=5) as response:
                    assert response.status == 200
                    collector = NavigationCollector()
                    collector.feed(response.read().decode("utf-8"))
                destinations = {url_parse.urljoin(page_url, href) for href in collector.links}
                assert destinations == expected_urls
                assert [url_parse.urljoin(page_url, href) for href in collector.active_links] == [
                    page_url
                ]
                for destination in destinations:
                    with request.urlopen(destination, timeout=5) as response:
                        assert response.status == 200
        finally:
            server.shutdown()
            worker.join(timeout=5)
        assert not worker.is_alive()


@pytest.mark.parametrize(
    ("filename", "title"),
    [
        ("plan/overview.html", "Overview"),
        ("plan/graph.html", "Execution graph"),
        ("plan/stages.html", "Stages"),
    ],
)
def test_execution_plan_pages_render_only_their_section(
    tmp_path: pathlib.Path, filename: str, title: str
) -> None:
    specification = spec.Specification.from_json(SPEC_PATH)
    docs.Documentation(specification).create_html(tmp_path / "index.html")
    document = (tmp_path / filename).read_text(encoding="utf-8")

    assert 'aria-label="Execution plan sections"' in document
    is_graph = title == "Execution graph"
    assert heading_titles(document) == [title]
    if is_graph:
        assert 'class="absolute inset-0"' in document
        assert "<header" not in document
        assert ">Callable graph</h2>" not in document
        assert ".linkDirectionalParticles(2)" in document
        assert ".linkDirectionalArrow" not in document
        assert 'class="details details-2d"' in document
        if is_graph:
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
                "  ],",
                '  dataset="pump_telemetry_dataset",',
                '  output="operating_point_recommendation"',
                ")",
            ]
            assert f'"label_lines": {json.dumps(expected_list_lines)}' in document
            expected_object_lines = [
                "maximum(",
                '  feature="bearing_temperature",',
                '  dataset="pump_telemetry_dataset",',
                "  dimensions=[",
                '    "plant",',
                '    "production_line",',
                '    "pump"',
                "  ],",
                '  output="bearing_temperature_max"',
                ")",
            ]
            assert f'"label_lines": {json.dumps(expected_object_lines)}' in document
            assert ".nodeLabel(node => node.label)" in document
            assert "node.label_lines.forEach((line, index) =>" in document
            assert "const rank = node.stage - 1" in document
            graph_data_match = re.search(
                r"const callableGraphData = (.*?);\n\t\tconst callableNodeDetails",
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
    assert ('id="callable-graph"' in document) == is_graph
    assert ("const callableGraphData" in document) == is_graph
    assert ('id="operations"' in document) == (title == "Stages")
    assert (">Argument</th>" in document) == (title == "Stages")
    if title == "Stages":
        assert "Source dataset:" not in document
        assert "Group by target entity dimensions:" not in document
        assert "bearing_temperature_max" in document
    assert ("3d-force-graph.min.js" in document) == is_graph
    assert ("force-graph@1.52.0" in document) == is_graph


@pytest.mark.parametrize("filename", ["graph/feature_graph.html", "plan/graph.html"])
def test_graph_pages_have_one_selector_and_shared_data(
    tmp_path: pathlib.Path, filename: str
) -> None:
    docs.create_html(spec.Specification.from_json(SPEC_PATH), tmp_path / "index.html")
    document = (tmp_path / filename).read_text(encoding="utf-8")

    assert document.count('aria-label="Graph view"') == 1
    assert 'data-dimension="2d" aria-pressed="true" aria-controls="graph-2d"' in document
    assert 'data-dimension="3d" aria-pressed="false" aria-controls="graph-3d"' in document
    assert 'id="graph-3d" class="graph-view" hidden' in document
    assert 'id="graph-error" role="alert" hidden' in document
    assert "showView('2d')" in document
    assert "JSON.parse(JSON.stringify(sourceData))" in document
    assert "pauseAnimation()" in document
    assert "resumeAnimation()" in document
    assert "node.id === selectedId" in document
    assert "console.error(" in document
    assert "Unable to display the" in document
    assert document.count('"nodes":') == 1
    assert len(re.findall(r"<h1[ >]", document)) == 1
    assert "feature_graph_2d.html" not in document
    assert "execution_plan_graph_3d.html" not in document


def test_rebuild_removes_only_obsolete_graph_pages(tmp_path: pathlib.Path) -> None:
    obsolete = (
        "feature_graph_2d.html",
        "feature_graph_3d.html",
        "execution_plan_graph_2d.html",
        "execution_plan_graph_3d.html",
    )
    for filename in (*obsolete, "custom.html"):
        (tmp_path / filename).write_text("old", encoding="utf-8")
    docs.create_html(spec.Specification(), tmp_path / "index.html")
    assert all(not (tmp_path / filename).exists() for filename in obsolete)
    assert (tmp_path / "custom.html").read_text(encoding="utf-8") == "old"


def test_website_without_timestamp_is_deterministic(tmp_path: pathlib.Path) -> None:
    specification = spec.Specification.from_json(SPEC_PATH)
    first = docs.Documentation(specification).create_html(tmp_path / "first" / "index.html")
    second = docs.Documentation(specification).create_html(tmp_path / "second" / "index.html")

    for filename in ("index.html", *REPORTS):
        assert (first.parent / filename).read_bytes() == (second.parent / filename).read_bytes()


def test_execution_plan_overview_statistics_match_plan(tmp_path: pathlib.Path) -> None:
    specification = spec.Specification.from_json(SPEC_PATH)
    plan = compile.Compiler(specification).compile()
    docs.Documentation(specification).create_html(tmp_path / "index.html")
    document = (tmp_path / "plan/overview.html").read_text(encoding="utf-8")
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
        kind: str(count)
        for kind, count in collections.Counter(op.kind for op in plan.operations).items()
    }
    assert re.findall(r'data-stage="(\d+)" data-count="(\d+)"', document) == [
        (str(index), str(len(stage))) for index, stage in enumerate(plan.execution_stages, start=1)
    ]


def test_empty_execution_plan_overview_statistics(tmp_path: pathlib.Path) -> None:
    docs.Documentation(spec.Specification()).create_html(tmp_path / "index.html")
    document = (tmp_path / "plan/overview.html").read_text(encoding="utf-8")

    assert re.findall(r'data-value="(\d+)"', document) == ["0"] * 7
    assert "No callable operations." in document
    assert "No execution stages." in document


@pytest.mark.parametrize(
    "filename", ["overview.html", "features.html", "graph.html", "stages.html"]
)
def test_website_index_can_share_a_report_basename(tmp_path: pathlib.Path, filename: str) -> None:
    specification = spec.Specification.from_json(SPEC_PATH)

    index = docs.Documentation(specification).create_html(tmp_path / filename)
    assert index.is_file()
    for report in REPORTS:
        page = tmp_path / report
        assert page.is_file()
        collector = NavigationCollector()
        collector.feed(page.read_text(encoding="utf-8"))
        assert f"../{filename}" in collector.links
        assert [(page.parent / href).resolve() for href in collector.active_links] == [
            page.resolve()
        ]


def test_standalone_html_apis_are_removed() -> None:
    specification = spec.Specification.from_json(SPEC_PATH)
    graph = analytics.FeatureGraph(specification)
    assert not hasattr(specification, "create_html")
    assert not hasattr(graph, "export_html")
    assert not hasattr(graph.subset(["health_signal_normalized"]), "export_html")
    assert not hasattr(compile.Compiler(specification).compile(), "export_html")
    assert not hasattr(spec_render, "create_html")
    assert not hasattr(spec_render, "create_website_pages")
    assert not hasattr(graph_render, "render_graph_html")
    assert not hasattr(graph_render, "export_graph_html")


def test_website_propagates_compilation_errors_without_writing_reports(
    tmp_path: pathlib.Path,
) -> None:
    specification = spec.Specification.from_json(SPEC_PATH)
    specification.functions.read[
        "read_pump_telemetry"
    ].entrypoint = "missing_functions:read_pump_telemetry"

    with pytest.raises((ImportError, ValueError), match="missing_functions"):
        docs.Documentation(specification).create_html(tmp_path / "index.html")

    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    ("filename", "variable"),
    [
        ("graph/feature_graph.html", "data"),
        ("plan/graph.html", "callableGraphData"),
    ],
)
def test_website_graph_links_reference_exported_nodes(
    tmp_path: pathlib.Path, filename: str, variable: str
) -> None:
    specification = spec.Specification.from_json(SPEC_PATH)
    docs.Documentation(specification).create_html(tmp_path / "index.html")
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


def test_execution_plan_graphs_match_compiled_callable_dependencies(tmp_path: pathlib.Path) -> None:
    specification = spec.Specification.from_json(SPEC_PATH)
    plan = compile.Compiler(specification).compile()
    docs.Documentation(specification).create_html(tmp_path / "index.html")
    document = (tmp_path / "plan/graph.html").read_text(encoding="utf-8")
    match = re.search(r"const callableGraphData = (.+);", document)
    assert match is not None
    payload = json.loads(match.group(1))
    assert {node["id"] for node in payload["nodes"]} == {
        operation.id for operation in plan.operations
    }
    assert all(node["node_type"] == "callable" for node in payload["nodes"])
    assert {(link["source"], link["target"]) for link in payload["links"]} == {
        (dependency_id, operation.id)
        for operation in plan.operations
        for dependency_id in operation.dependency_ids
    }


def test_website_does_not_execute_analytics(tmp_path: pathlib.Path, monkeypatch) -> None:
    @functools.wraps(source.read_pump_telemetry)
    def fail_if_executed(*args: object, **kwargs: object) -> None:
        raise AssertionError("Website generation must not execute analytics")

    monkeypatch.setattr(source, "read_pump_telemetry", fail_if_executed)
    specification = spec.Specification.from_json(SPEC_PATH)

    assert docs.Documentation(specification).create_html(tmp_path / "index.html").is_file()


def test_website_can_include_specification_timestamp(tmp_path: pathlib.Path) -> None:
    specification = spec.Specification.from_json(SPEC_PATH)

    docs.Documentation(specification).create_html(
        tmp_path / "index.html", include_generated_at=True
    )

    assert re.search(
        r"generated \d{4}-\d{2}-\d{2}T",
        (tmp_path / "spec/overview.html").read_text(encoding="utf-8"),
    )
