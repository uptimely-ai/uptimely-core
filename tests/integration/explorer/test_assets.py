"""Validate external Explorer assets and page-specific graph configuration."""

import dataclasses
import json
import pathlib
import re
import shutil
from urllib import parse

import pytest
from conftest import EXAMPLES_ROOT, render_explorer

from uptimely import project, spec
from uptimely.explorer import graph_style, render
from uptimely.explorer.sections import feature_graph

ASSETS = {
    "css/base.css",
    "css/dashboard.css",
    "css/data_lineage.css",
    "css/graph.css",
    "css/icons.css",
    "css/spec.css",
    "js/invocation_graph.js",
    "js/data_lineage.js",
    "js/feature_graph.js",
    "js/graph_components.js",
    "js/icons.js",
    "js/tailwind_config.js",
    "js/view_controller.js",
}


@pytest.mark.parametrize("index_name", ["index.html", "custom.html"])
def test_external_assets_resolve_after_moving_website(
    tmp_path: pathlib.Path, index_name: str
) -> None:
    original = tmp_path / "original"
    destination = tmp_path / "projects/analytics"
    render_explorer(spec.Spec(), original / index_name)
    destination.parent.mkdir()
    shutil.move(original, destination)
    referenced_assets: set[str] = set()
    for page in destination.rglob("*.html"):
        document = page.read_text(encoding="utf-8")
        assert "<style" not in document
        assert all(
            'type="application/json"' in attributes or "src=" in attributes
            for attributes in re.findall(r"<script\b([^>]*)>", document)
        )
        for url in re.findall(r'(?:src|href)="([^"]+\.(?:js|css))"', document):
            if parse.urlsplit(url).scheme:
                continue
            asset = (page.parent / url).resolve()
            assert asset.is_relative_to(destination.resolve())
            assert asset.is_file()
            referenced_assets.add(asset.relative_to(destination.resolve()).as_posix())
            content = asset.read_text(encoding="utf-8")
            assert "{{" not in content
            assert "{%" not in content
    assert referenced_assets == ASSETS
    assert {
        path.relative_to(destination).as_posix()
        for directory in ("js", "css")
        for path in (destination / directory).iterdir()
    } == ASSETS


def test_graph_style_is_passed_as_json_without_changing_shared_script(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    style = graph_style.GraphStyle(
        background_color="#123456",
        function_color="#abcdef",
        link_width=2.5,
        charge_strength=-120,
    )
    monkeypatch.setattr(graph_style, "GraphStyle", lambda: style)
    feature_graph.SECTION.write_pages(
        tmp_path,
        render.WebsiteContext(),
        feature_graph.build_context(spec.FeatureGraph(spec.Spec())),
    )
    document = (tmp_path / "spec/graph.html").read_text(encoding="utf-8")
    match = re.search(
        r'<script id="graph-style" type="application/json">(.*?)</script>',
        document,
        re.DOTALL,
    )
    assert match is not None
    assert json.loads(match.group(1)) == dataclasses.asdict(style)
    assert 'style="--graph-background: #123456"' in document
    assert 'src="../js/feature_graph.js"' in document


def test_build_manifest_includes_all_explorer_assets() -> None:
    bundle = project.load_build_bundle(EXAMPLES_ROOT / "pump_analytics")
    assert set(bundle.manifest.explorer_files) >= ASSETS
    for filename in ASSETS:
        assert (bundle.explorer_path / filename).is_file()
