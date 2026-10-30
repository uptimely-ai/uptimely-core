"""Validate external Explorer assets and page-specific graph configuration."""

import dataclasses
import json
import pathlib
import re
import shutil
from urllib import parse

import pytest
from support import examples as example_support
from support import rendering as rendering_support

from uptimely import compiler, project, spec
from uptimely.explorer import graph_style, render
from uptimely.explorer.sections import feature_lineage

ASSETS = {
    "css/base.css",
    "css/dashboard.css",
    "css/data_lineage.css",
    "css/graph.css",
    "css/icons.css",
    "css/spec.css",
    "js/invocation_lineage.js",
    "js/data_lineage.js",
    "js/feature_lineage.js",
    "js/lineage_config.js",
    "js/lineage_components.js",
    "js/lineage_layout.js",
    "js/icons.js",
    "js/code_highlight.js",
    "js/catalog_context.js",
    "js/tailwind_config.js",
    "js/lineage_view_controller.js",
}


@pytest.mark.parametrize("index_name", ["index.html", "custom.html"])
def test_external_assets_resolve_after_moving_website(
    tmp_path: pathlib.Path, index_name: str
) -> None:
    original = tmp_path / "original"
    destination = tmp_path / "projects/analytics"
    spec_definition = spec.Spec()
    rendering_support.render_explorer(
        spec_definition, original / index_name, plan=compiler.Compiler().compile(spec_definition)
    )
    destination.parent.mkdir()
    shutil.move(original, destination)
    referenced_assets: set[str] = set()
    pending_modules: list[pathlib.Path] = []
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
            if asset.suffix == ".js":
                pending_modules.append(asset)
    checked_modules: set[pathlib.Path] = set()
    while pending_modules:
        module = pending_modules.pop()
        if module in checked_modules:
            continue
        checked_modules.add(module)
        content = module.read_text(encoding="utf-8")
        for import_path in re.findall(r'\bfrom\s+["\']([^"\']+)["\']', content):
            asset = (module.parent / import_path).resolve()
            assert asset.is_relative_to(destination.resolve())
            assert asset.is_file()
            referenced_assets.add(asset.relative_to(destination.resolve()).as_posix())
            pending_modules.append(asset)
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
    feature_lineage.SECTION.write_pages(
        tmp_path,
        render.WebsiteContext(),
        feature_lineage.build_context(spec.FeatureGraph(spec.Spec())),
    )
    document = (tmp_path / "spec/feature-lineage.html").read_text(encoding="utf-8")
    match = re.search(
        r'<script id="graph-style" type="application/json">(.*?)</script>',
        document,
        re.DOTALL,
    )
    assert match is not None
    assert json.loads(match.group(1)) == dataclasses.asdict(style)
    assert 'style="--lineage-background: #123456"' in document
    assert 'src="../js/feature_lineage.js"' in document


@pytest.mark.usefixtures("example_projects")
def test_build_manifest_includes_all_explorer_assets() -> None:
    bundle = project.load_build_bundle(example_support.EXAMPLES_ROOT / "pump_analytics")
    assert set(bundle.manifest.explorer_files) >= ASSETS
    for filename in ASSETS:
        assert (bundle.explorer_path / filename).is_file()
