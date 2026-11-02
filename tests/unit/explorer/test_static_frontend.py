"""Tests for the packaged Explorer frontend and restored browser components."""

import importlib.resources


def test_static_frontend_uses_packaged_assets_and_live_api() -> None:
    frontend = importlib.resources.files("uptimely.explorer").joinpath("app", "static")
    index = frontend.joinpath("index.html").read_text(encoding="utf-8")
    config = frontend.joinpath("config.js").read_text(encoding="utf-8")
    script = frontend.joinpath("js", "app.js").read_text(encoding="utf-8")

    assert 'src="./config.js"' in index
    assert 'src="./js/app.js"' in index
    assert 'dataUrl: "/api/explorer"' in config
    assert 'class="with-navigation bg-slate-950"' in index
    assert "tailwindcss.com/3.4.17" in index
    assert "force-graph@1.52.0" in script
    assert "3d-force-graph@1.77.0" in script
    assert "hashchange" in script
    assert "textContent" in script
    assert "Loading Explorer data" in index
    assert "errorStatus" in script
    assert script.count("fetch(") == 1
    assert "fetch(configuration.dataUrl" in script
    assert "data/explorer.json" not in script


def test_original_ui_components_are_packaged_with_the_static_frontend() -> None:
    frontend = importlib.resources.files("uptimely.explorer").joinpath("app", "static")
    for name in ("base", "icons", "dashboard", "spec", "graph", "data_lineage"):
        assert frontend.joinpath("css", f"{name}.css").is_file()
    for name in (
        "catalog_context",
        "icons",
        "feature_lineage",
        "invocation_lineage",
        "lineage_components",
        "lineage_view_controller",
        "data_lineage",
        "data_lineage/tables",
        "data_lineage/links",
        "data_lineage/viewport",
    ):
        assert frontend.joinpath("js", f"{name}.js").is_file()
