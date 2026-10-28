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
from conftest import EXAMPLES_ROOT, plan_for_spec, render_explorer
from examples.pump_analytics.functions import analytics

from uptimely import compiler, spec
from uptimely.explorer import graph_render, spec_render

SPEC_PATH = EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json"
REPORTS = {
    "spec/overview.html": "spec",
    "spec/features.html": "features",
    "spec/entities.html": "entities",
    "spec/datasets.html": "datasets",
    "spec/dimensions.html": "dimensions",
    "spec/functions.html": "functions",
    "spec/graph.html": "graph",
    "plan/overview.html": "plan",
    "plan/graph.html": "plan",
    "plan/stages.html": "stages",
    "execution/data_lineage.html": "lineage",
}


class NavigationCollector(html_parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_navigation = False
        self.links: list[str] = []
        self.assets: list[str] = []
        self.active_links: list[str] = []
        self.html_count = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        asset = None
        if tag == "script":
            asset = attributes.get("src")
        elif tag == "link" and attributes.get("rel") == "stylesheet":
            asset = attributes.get("href")
        if asset and not url_parse.urlsplit(asset).scheme:
            self.assets.append(asset)
        if tag == "html":
            self.html_count += 1
        if tag == "nav" and attributes.get("aria-label") == "Explorer pages":
            self.in_navigation = True
        if tag == "a" and (self.in_navigation or attributes.get("class") == "site-product"):
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
    render_explorer(spec.Spec(), tmp_path / "index.html")
    expected = {
        "index.html": ("home", "house", "Untitled analytics project"),
        "spec/overview.html": ("overview", "layout-dashboard", "Overview"),
        "spec/features.html": ("features", "sparkles", "Features"),
        "spec/entities.html": ("entities", "boxes", "Entities"),
        "spec/datasets.html": ("datasets", "table", "Datasets"),
        "spec/dimensions.html": ("dimensions", "layers-3", "Dimensions"),
        "spec/functions.html": ("functions", "braces", "Functions"),
        "spec/graph.html": ("feature-graph", "network", "Feature lineage"),
        "plan/overview.html": ("overview", "layout-dashboard", "Overview"),
        "plan/graph.html": ("execution-graph", "workflow", "Execution graph"),
        "plan/stages.html": ("stages", "list-ordered", "Stages"),
        "execution/data_lineage.html": ("lineage", "database-zap", "Data lineage"),
    }
    palette = {
        "home": "#93c5fd",
        "spec": "#67e8f9",
        "plan": "#fcd34d",
        "overview": "#93c5fd",
        "features": "#f9a8d4",
        "entities": "#fdba74",
        "datasets": "#6ee7b7",
        "dimensions": "#818cf8",
        "functions": "#fcd34d",
        "lineage": "#e879f9",
        "feature-graph": "#2dd4bf",
        "invocations": "#fcd34d",
        "execution": "#e879f9",
        "execution-graph": "#fb923c",
        "stages": "#818cf8",
    }
    icon_styles = (tmp_path / "css/icons.css").read_text(encoding="utf-8")
    base_styles = (tmp_path / "css/base.css").read_text(encoding="utf-8")
    for icon_key, color in palette.items():
        assert f".icon--{icon_key} {{ --icon-color: {color};" in icon_styles
    assert ".site-icon { color: var(--icon-color);" in base_styles
    assert re.search(
        r'a\[aria-current="page"\] \{[^}]*background: #1e293b;'
        r"[^}]*box-shadow: inset 3px 0 #94a3b8;",
        base_styles,
    )
    assert "a:focus-visible" in base_styles
    for filename, (key, symbol, title) in expected.items():
        document = (tmp_path / filename).read_text(encoding="utf-8")
        collector = IconCollector()
        collector.feed(document)
        assert collector.headings == [title]
        assert len(collector.heading_icons) == 1
        heading_icon = collector.heading_icons[0]
        assert heading_icon["data-lucide"] == symbol
        assert f"icon--{key}" in (heading_icon["class"] or "").split()
        if key != "home":
            assert any(
                item["data-lucide"] == symbol and f"icon--{key}" in (item["class"] or "").split()
                for item in collector.navigation_icons
            )
        assert all(item["aria-hidden"] == "true" for item in collector.icons)
        navigation = re.search(r"<nav\b.*?</nav>", document, re.DOTALL)
        assert navigation is not None
        assert re.findall(
            r'class="site-icon icon--(\S+) nav-icon"[^>]*></i><span>([^<]+)</span>',
            navigation.group(),
        ) == [
            ("spec", "Spec"),
            ("overview", "Overview"),
            ("features", "Features"),
            ("entities", "Entities"),
            ("datasets", "Datasets"),
            ("dimensions", "Dimensions"),
            ("functions", "Functions"),
            ("feature-graph", "Feature graph"),
            ("plan", "Plan"),
            ("overview", "Overview"),
            ("execution-graph", "Execution graph"),
            ("stages", "Stages"),
            ("execution", "Execution"),
            ("lineage", "Data lineage"),
        ]
        navigation_symbols = {
            next(
                part.removeprefix("icon--")
                for part in (item["class"] or "").split()
                if part.startswith("icon--")
            ): item["data-lucide"]
            for item in collector.navigation_icons
        }
        assert navigation_symbols["plan"] == "list-tree"
        assert navigation_symbols["execution"] == "play"
        assert navigation_symbols["feature-graph"] == "network"
        assert navigation_symbols["execution-graph"] == "workflow"
        assert navigation_symbols["lineage"] == "database-zap"

    plan_overview = (tmp_path / "plan/overview.html").read_text(encoding="utf-8")
    assert re.findall(
        r'data-stat="([^"]+)">.*?class="site-icon icon--(\S+) nav-icon"',
        plan_overview,
        re.DOTALL,
    ) == [
        ("Invocations", "invocations"),
        ("Functions", "functions"),
        ("Entities", "entities"),
        ("Features", "features"),
        ("Stages", "stages"),
        ("Dependencies", "execution-graph"),
        ("Max parallel invocations", "stages"),
    ]


def test_icon_palette_contrast(tmp_path: pathlib.Path) -> None:
    """Keep concept colors legible on normal and selected navigation backgrounds."""
    render_explorer(spec.Spec(), tmp_path / "index.html")
    icon_styles = (tmp_path / "css/icons.css").read_text(encoding="utf-8")
    colors = set(re.findall(r"--icon-color: (#[0-9a-f]{6});", icon_styles))
    assert len(colors) == 10
    for background in ("#0f172a", "#1e293b"):
        for color in colors:
            luminances = []
            for hex_color in (color, background):
                channels = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
                linear = [
                    value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
                    for value in channels
                ]
                luminances.append(
                    sum(w * c for w, c in zip((0.2126, 0.7152, 0.0722), linear, strict=True))
                )
            foreground_luminance, background_luminance = luminances
            contrast = (foreground_luminance + 0.05) / (background_luminance + 0.05)
            assert contrast >= 3, (color, background, contrast)


def test_website_exports_all_reports_with_relative_navigation(
    tmp_path: pathlib.Path, monkeypatch
) -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    monkeypatch.chdir(tmp_path)

    index = render_explorer(spec_definition)

    assert index == pathlib.Path("_generated/explorer/index.html")
    assert {path.name for path in index.parent.iterdir()} == {
        "index.html",
        "spec",
        "plan",
        "execution",
        "css",
        "js",
    }
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
    assert datasets.count("data-dataset-schema=") == 3
    assert "schema only, no sample records" in datasets
    assert datasets.count('<details class="mt-6 border-t border-slate-800 pt-4">') == 3
    assert "<summary" in datasets
    assert "Dataset details</summary>" in datasets
    assert "Blue: dimensions" not in datasets
    assert "row keys" not in datasets
    assert "discharge_pressure" in datasets
    assert "float · bar" in datasets
    assert "bg-[#172b46] text-[#b5d4f8]" in datasets
    assert "bg-[#15352e] text-[#a5dfca]" in datasets
    assert "bg-[#392e19] text-[#efcf89]" in datasets
    assert "Column metadata" not in datasets
    assert "Type / unit" not in datasets
    for entity in spec_definition.entities.values():
        for dataset in entity.datasets.values():
            table = re.search(
                rf'<table data-dataset-schema="{dataset.id}".*?</table>', datasets, re.DOTALL
            ).group()
            column_row, type_row = re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.DOTALL)
            columns = re.findall(r'<th scope="col"[^>]*>(.*?)</th>', column_row, re.DOTALL)
            entity_dimensions = entity.dimension_ids
            expected_names = [
                *entity_dimensions,
                *(name for name in dataset.features if name not in entity_dimensions),
            ]
            assert [column.split("<span", 1)[0] for column in columns] == expected_names
            assert len(re.findall(r"<td\b", type_row)) == len(columns)
            raw_columns = {
                name
                for action in dataset.actions.values()
                if spec_definition.functions[action.binding.function].kind
                in {"read", "conform", "expand"}
                for name in action.output_features
            }
            external_columns = {
                name
                for action in dataset.actions.values()
                if spec_definition.functions[action.binding.function].kind == "escape"
                for name in action.output_features
            }
            for name, column in zip(expected_names, columns, strict=True):
                if name in entity_dimensions:
                    assert ">Dimension</span>" in column
                elif name in raw_columns:
                    assert ">Raw</span>" in column
                elif name in external_columns:
                    assert ">External</span>" in column
                else:
                    assert ">Feature</span>" in column
            assert table.count("health_signal_normalized") <= 1
            assert table.count("pressure_flow_efficiency") <= 1
    assert "bg-blue-950" not in datasets
    assert "bg-teal-950" not in datasets
    assert "bg-violet-950" not in datasets
    assert "bg-amber-950" not in datasets
    assert 'class="dataset-table-scroll overflow-x-auto' in datasets
    spec_styles = (index.parent / "css/spec.css").read_text(encoding="utf-8")
    assert "scrollbar-width: thin" in spec_styles
    assert "scrollbar-color: #475569 #0f172a" in spec_styles
    assert ".dataset-table-scroll::-webkit-scrollbar" in spec_styles
    assert "Pump analytics" in (index.parent / "spec/overview.html").read_text(encoding="utf-8")
    graph_2d = (index.parent / "spec/graph.html").read_text(encoding="utf-8")
    assert '"label": "health_signal_normalized"' in graph_2d
    assert "force-graph@1.52.0/dist/force-graph.min.js" in graph_2d
    graph_script = (index.parent / "js/feature_graph.js").read_text(encoding="utf-8")
    assert ".height(graphContainer.clientHeight)" in graph_script
    assert "3d-force-graph" in graph_2d
    assert 'aria-label="Feature graph views"' not in graph_2d
    assert re.search(
        r'href="../spec/graph.html" aria-current="page">'
        r'<i class="site-icon icon--feature-graph nav-icon" '
        r'data-lucide="network"',
        graph_2d,
    )
    assert "ExplorerGraph.createView(graph, graphContainer, 80, '2d')" in graph_script
    plan = (index.parent / "plan/graph.html").read_text(encoding="utf-8")
    assert 'id="invocation-graph"' in plan
    assert "normalize_health_signal" in plan
    assert not pathlib.Path("_generated/spec").exists()
    assert not pathlib.Path("_generated/compile").exists()


def test_feature_graph_payload_uses_explorer_graph_renderer() -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    graph = spec.FeatureGraph(spec_definition)

    nodes, links = graph_render.graph_payload_from_cytoscape(graph)

    node_ids = {node["id"] for node in nodes}
    assert "health_signal_normalized" in node_ids
    assert any(
        link["source"] == "function:spec:normalize_health_signal"
        and link["target"] == "health_signal_normalized"
        for link in links
    )


def test_homepage_shows_project_counts_and_journey(tmp_path: pathlib.Path, monkeypatch) -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    expected_plan = plan_for_spec(spec_definition)

    def fail_compile(*args: object, **kwargs: object) -> None:
        pytest.fail("Example rendering must reuse the saved plan")

    monkeypatch.setattr(compiler.Compiler, "compile", fail_compile)
    index = render_explorer(spec_definition, tmp_path / "index.html")
    document = index.read_text(encoding="utf-8")

    assert "<title>Pump analytics | OpenAnalytics</title>" in document
    assert heading_titles(document) == ["Pump analytics"]
    datasets = [
        dataset
        for entity in spec_definition.entities.values()
        for dataset in entity.datasets.values()
    ]
    assert dict(re.findall(r'data-stat="([^"]+)" data-value="(\d+)"', document)) == {
        "Entities": str(len(spec_definition.entities)),
        "Datasets": str(len(datasets)),
        "Features": str(sum(len(dataset.features) for dataset in datasets)),
        "Functions": str(len(spec_definition.functions)),
        "Invocations": str(len(expected_plan.invocations)),
        "Stages": str(len(expected_plan.execution_stages)),
    }
    assert "Spec 3" in document
    assert 'aria-label="Project counts"' in document
    assert 'aria-label="Spec journey"' in document
    assert re.findall(r'<li class="journey-step (\S+) icon--\1">', document) == [
        "spec",
        "plan",
        "execution",
    ]
    for href, action in (
        ("spec/overview.html", "Explore spec"),
        ("plan/overview.html", "Inspect the plan"),
        ("execution/data_lineage.html", "Explore execution"),
    ):
        assert f'<a href="{href}">{action}' in document
        assert (index.parent / href).is_file()
    assert re.findall(r"<h3>(.*?)</h3>", document) == ["Spec", "Plan", "Execution"]
    assert "does not run analytical operations" in document
    assert "prefers-reduced-motion: reduce" in (tmp_path / "css/dashboard.css").read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize("name", [None, "", '<script>alert("title")</script> & Spec'])
def test_homepage_handles_unnamed_and_escaped_projects(
    tmp_path: pathlib.Path, name: str | None
) -> None:
    index = render_explorer(spec.Spec(name=name), tmp_path / "index.html")
    document = index.read_text(encoding="utf-8")

    assert re.findall(r'data-value="(\d+)"', document) == ["0"] * 6
    if not name:
        assert heading_titles(document) == ["Untitled analytics project"]
    else:
        assert (
            "<span>&lt;script&gt;alert(&#34;title&#34;)&lt;/script&gt; &amp; Spec</span>"
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
def test_spec_pages_render_only_their_section(
    tmp_path: pathlib.Path, filename: str, section_id: str, title: str
) -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    render_explorer(spec_definition, tmp_path / "index.html")
    document = (tmp_path / filename).read_text(encoding="utf-8")

    for candidate in ("overview", "entities", "datasets", "dimensions", "functions"):
        assert (f'<section id="{candidate}"' in document) == (candidate == section_id)
    assert 'aria-label="Spec sections"' in document
    assert 'aria-label="Documentation sections"' not in document
    headings = re.findall(r'<h1 class="([^"]+)">.*?<span>([^<]+)</span></h1>', document)
    assert len(headings) == 1
    assert headings[0][0] == (
        "title-with-icon font-display text-3xl font-semibold tracking-tight text-white"
    )
    assert headings[0][1] == title
    assert "sm:text-6xl" not in document


def test_spec_overview_displays_source_profile(tmp_path: pathlib.Path) -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    render_explorer(spec_definition, tmp_path / "index.html")
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
    spec_definition = spec.load_spec(SPEC_PATH)

    index = render_explorer(spec_definition, tmp_path / "nested" / "spec.htm")

    assert index == tmp_path / "nested" / "spec.html"
    assert index.is_file()
    assert all((index.parent / filename).is_file() for filename in REPORTS)
    for filename in (index.name, *REPORTS):
        parser = NavigationCollector()
        page_file = index.parent / filename
        parser.feed(page_file.read_text(encoding="utf-8"))
        assert ("spec.html" if filename == index.name else "../spec.html") in parser.links
        assert "index.html" not in parser.links
        assert [(page_file.parent / href).resolve() for href in parser.active_links] == [
            page_file.resolve()
        ]
        assert all((page_file.parent / href).is_file() for href in parser.links)


@pytest.mark.parametrize("index_name", ["index.html", "spec.html"])
def test_relocated_website_navigation_works_under_url_prefix(
    tmp_path: pathlib.Path, index_name: str
) -> None:
    original = tmp_path / "generated"
    render_explorer(spec.Spec(), original / index_name)
    host_root = tmp_path / "hosted"
    relocated = host_root / "projects" / "spec"
    relocated.parent.mkdir(parents=True)
    original.rename(relocated)
    handler = functools.partial(http_server.SimpleHTTPRequestHandler, directory=str(host_root))
    with http_server.ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
        worker = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
        worker.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}/projects/spec/"
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
                for asset in collector.assets:
                    with request.urlopen(url_parse.urljoin(page_url, asset), timeout=5) as response:
                        assert response.status == 200
                        assert response.headers.get_content_type() in {
                            "text/css",
                            "text/javascript",
                            "application/javascript",
                        }
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
    spec_definition = spec.load_spec(SPEC_PATH)
    render_explorer(spec_definition, tmp_path / "index.html")
    document = (tmp_path / filename).read_text(encoding="utf-8")

    assert 'aria-label="Plan sections"' in document
    is_graph = title == "Execution graph"
    assert heading_titles(document) == [title]
    if is_graph:
        script = (tmp_path / "js/invocation_graph.js").read_text(encoding="utf-8")
        assert 'class="absolute inset-0"' in document
        assert document.count("<header") == 1
        assert '<header class="site-topbar"' in document
        assert ">Invocation graph</h2>" not in document
        assert ".linkDirectionalParticles(2)" in script
        assert ".linkDirectionalArrowLength(style.arrow_length)" in script
        assert ".linkDirectionalArrowRelPos(style.arrow_rel_pos)" in script
        assert 'class="details details-2d"' in document
        if is_graph:
            assert (
                "ExplorerGraph.createView(invocationGraph, invocationGraphContainer, 140, '2d')"
                in script
            )
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
                '  dataset="pump_telemetry_dataset",',
                "  optimization_features=[",
                '    "discharge_pressure",',
                '    "flow_rate",',
                '    "motor_power",',
                '    "bearing_temperature",',
                '    "vibration_rms"',
                "  ],",
                '  output="operating_point_recommendation"',
                ")",
            ]
            assert f'"label_lines": {json.dumps(expected_list_lines)}' in document
            expected_object_lines = [
                "maximum(",
                '  dataset="pump_telemetry_dataset",',
                '  feature="bearing_temperature",',
                "  dimensions=[",
                '    "plant",',
                '    "production_line",',
                '    "pump"',
                "  ],",
                '  output="bearing_temperature_max"',
                ")",
            ]
            assert f'"label_lines": {json.dumps(expected_object_lines)}' in document
            assert ".nodeLabel(node => ExplorerGraph.tooltip(node.label))" in script
            assert "node.label_lines.forEach((line, index) =>" in script
            assert "const rank = node.stage - 1" in script
            graph_data_match = re.search(
                r'<script id="graph-data" type="application/json">(.*?)</script>',
                document,
                re.DOTALL,
            )
            assert graph_data_match is not None
            graph_nodes = json.loads(graph_data_match.group(1))["nodes"]
            normalize_node = next(
                node for node in graph_nodes if node["function_id"] == "normalize_health_signal"
            )
            assert normalize_node["stage"] == 3
            assert "Stage ${stage + 1}" in script
            assert ".onRenderFramePre(drawStageLanes)" in script
            assert "ctx.fillRect(left, -laneHeight / 2, 360, laneHeight)" in script
    assert ('id="plan-overview"' in document) == (title == "Overview")
    assert ('id="invocation-graph"' in document) == is_graph
    assert ('src="../js/invocation_graph.js"' in document) == is_graph
    assert ('id="invocations"' in document) == (title == "Stages")
    assert (">Argument</th>" in document) == (title == "Stages")
    if title == "Stages":
        assert "Source dataset:" not in document
        assert "Group by target entity dimensions:" not in document
        assert "bearing_temperature_max" in document
    assert ("3d-force-graph.min.js" in document) == is_graph
    assert ("force-graph@1.52.0" in document) == is_graph


@pytest.mark.parametrize("filename", ["spec/graph.html", "plan/graph.html"])
def test_graph_pages_have_one_selector_and_shared_data(
    tmp_path: pathlib.Path, filename: str
) -> None:
    render_explorer(spec.load_spec(SPEC_PATH), tmp_path / "index.html")
    document = (tmp_path / filename).read_text(encoding="utf-8")

    assert document.count('aria-label="Graph view"') == 1
    assert document.count('aria-label="Graph zoom"') == 1
    assert re.search(
        r'<div class="graph-title-controls">\s*<h1\b.*?</h1>\s*'
        r'<div class="graph-buttons" role="group" aria-label="Graph view">',
        document,
        re.DOTALL,
    )
    assert 'aria-label="Zoom in"' in document
    assert 'aria-label="Zoom out"' in document
    assert '<details class="panel" open>' in document
    assert document.index('src="../js/graph_components.js"') < document.index(
        'src="../js/view_controller.js"'
    )
    assert 'data-dimension="2d" aria-pressed="true" aria-controls="graph-2d"' in document
    assert 'data-dimension="3d" aria-pressed="false" aria-controls="graph-3d"' in document
    assert 'id="graph-3d" class="graph-view" hidden' in document
    assert 'id="graph-error" role="alert" hidden' in document
    controller = (tmp_path / "js/view_controller.js").read_text(encoding="utf-8")
    assert 'src="../js/view_controller.js"' in document
    assert "showView('2d')" in controller
    assert "JSON.parse(JSON.stringify(sourceData))" in controller
    assert "pauseAnimation()" in controller
    assert "resumeAnimation()" in controller
    assert "node.id === selectedId" in controller
    assert "console.error(" in controller
    assert "Unable to display the" in controller
    assert "new ResizeObserver(" in controller
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
        "graph/feature_graph.html",
    )
    for filename in (*obsolete, "custom.html"):
        (tmp_path / filename).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / filename).write_text("old", encoding="utf-8")
    (tmp_path / "graph/custom.html").write_text("custom graph", encoding="utf-8")
    render_explorer(spec.Spec(), tmp_path / "index.html")
    assert all(not (tmp_path / filename).exists() for filename in obsolete)
    assert (tmp_path / "custom.html").read_text(encoding="utf-8") == "old"
    assert (tmp_path / "graph/custom.html").read_text(encoding="utf-8") == "custom graph"
    assert (tmp_path / "spec/graph.html").is_file()


def test_website_without_timestamp_is_deterministic(tmp_path: pathlib.Path) -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    first = render_explorer(spec_definition, tmp_path / "first" / "index.html")
    second = render_explorer(spec_definition, tmp_path / "second" / "index.html")

    first_files = {
        path.relative_to(first.parent): path.read_bytes()
        for path in first.parent.rglob("*")
        if path.is_file()
    }
    second_files = {
        path.relative_to(second.parent): path.read_bytes()
        for path in second.parent.rglob("*")
        if path.is_file()
    }
    assert first_files == second_files


def test_execution_plan_overview_statistics_match_plan(tmp_path: pathlib.Path) -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    plan = plan_for_spec(spec_definition)
    render_explorer(spec_definition, tmp_path / "index.html")
    document = (tmp_path / "plan/overview.html").read_text(encoding="utf-8")
    cards = dict(re.findall(r'data-stat="([^"]+)"[\s\S]*?data-value="(\d+)"', document))
    assert cards == {
        "Invocations": str(len(plan.invocations)),
        "Functions": str(len({invocation.function_id for invocation in plan.invocations})),
        "Entities": str(len({invocation.entity_id for invocation in plan.invocations})),
        "Features": str(
            len(
                {
                    feature
                    for invocation in plan.invocations
                    if invocation.function_kind == "vectorize"
                    for feature in invocation.output_features
                }
            )
        ),
        "Stages": str(len(plan.execution_stages)),
        "Dependencies": str(sum(len(invocation.dependency_ids) for invocation in plan.invocations)),
        "Max parallel invocations": str(max(map(len, plan.execution_stages), default=0)),
    }
    assert dict(re.findall(r'data-function-kind="([^"]+)" data-count="(\d+)"', document)) == {
        kind: str(count)
        for kind, count in collections.Counter(
            item.function_kind for item in plan.invocations
        ).items()
    }
    assert re.findall(r'data-stage="(\d+)" data-count="(\d+)"', document) == [
        (str(index), str(len(stage))) for index, stage in enumerate(plan.execution_stages, start=1)
    ]


def test_empty_execution_plan_overview_statistics(tmp_path: pathlib.Path) -> None:
    render_explorer(spec.Spec(), tmp_path / "index.html")
    document = (tmp_path / "plan/overview.html").read_text(encoding="utf-8")

    assert re.findall(r'data-value="(\d+)"', document) == ["0"] * 7
    assert "No invocations." in document
    assert "No execution stages." in document


@pytest.mark.parametrize(
    "filename", ["overview.html", "features.html", "graph.html", "stages.html"]
)
def test_website_index_can_share_a_report_basename(tmp_path: pathlib.Path, filename: str) -> None:
    spec_definition = spec.load_spec(SPEC_PATH)

    index = render_explorer(spec_definition, tmp_path / filename)
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
    spec_definition = spec.load_spec(SPEC_PATH)
    graph = spec.FeatureGraph(spec_definition)
    assert not hasattr(spec_definition, "create_html")
    assert not hasattr(graph, "export_html")
    assert not hasattr(graph.subset(["health_signal_normalized"]), "export_html")
    assert not hasattr(plan_for_spec(spec_definition), "export_html")
    assert not hasattr(spec_render, "create_html")
    assert not hasattr(spec_render, "create_website_pages")
    assert not hasattr(graph_render, "render_graph_html")
    assert not hasattr(graph_render, "export_graph_html")


def test_website_propagates_compilation_errors_without_writing_reports(
    tmp_path: pathlib.Path,
) -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    spec_definition.functions[
        "read_pump_telemetry"
    ].entrypoint = "missing_functions:read_pump_telemetry"

    with pytest.raises((ImportError, ValueError), match="missing_functions"):
        render_explorer(spec_definition, tmp_path / "index.html")

    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "filename",
    ["spec/graph.html", "plan/graph.html"],
)
def test_website_graph_links_reference_exported_nodes(
    tmp_path: pathlib.Path, filename: str
) -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    render_explorer(spec_definition, tmp_path / "index.html")
    document = (tmp_path / filename).read_text(encoding="utf-8")
    match = re.search(
        r'<script id="graph-data" type="application/json">(.*?)</script>', document, re.DOTALL
    )
    assert match is not None
    payload = json.loads(match.group(1))
    identifiers = {node["id"] for node in payload["nodes"]}

    assert identifiers
    assert payload["links"]
    assert len(identifiers) == len(payload["nodes"])
    for link in payload["links"]:
        assert link["source"] in identifiers
        assert link["target"] in identifiers


def test_execution_plan_graphs_match_compiled_invocation_dependencies(
    tmp_path: pathlib.Path,
) -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    plan = plan_for_spec(spec_definition)
    render_explorer(spec_definition, tmp_path / "index.html")
    document = (tmp_path / "plan/graph.html").read_text(encoding="utf-8")
    match = re.search(
        r'<script id="graph-data" type="application/json">(.*?)</script>', document, re.DOTALL
    )
    assert match is not None
    payload = json.loads(match.group(1))
    assert {node["id"] for node in payload["nodes"]} == {
        invocation.id for invocation in plan.invocations
    }
    assert all(node["node_type"] == "invocation" for node in payload["nodes"])
    assert {(link["source"], link["target"]) for link in payload["links"]} == {
        (dependency_id, invocation.id)
        for invocation in plan.invocations
        for dependency_id in invocation.dependency_ids
    }


def test_website_does_not_execute_spec(tmp_path: pathlib.Path, monkeypatch) -> None:
    @functools.wraps(analytics.read_pump_telemetry)
    def fail_if_executed(*args: object, **kwargs: object) -> None:
        raise AssertionError("Website generation must not execute spec")

    monkeypatch.setattr(analytics, "read_pump_telemetry", fail_if_executed)
    spec_definition = spec.load_spec(SPEC_PATH)

    assert render_explorer(spec_definition, tmp_path / "index.html").is_file()


def test_website_can_include_spec_timestamp(tmp_path: pathlib.Path) -> None:
    spec_definition = spec.load_spec(SPEC_PATH)

    render_explorer(spec_definition, tmp_path / "index.html", include_generated_at=True)

    assert re.search(
        r"generated \d{4}-\d{2}-\d{2}T",
        (tmp_path / "spec/overview.html").read_text(encoding="utf-8"),
    )
