"""Tests for the packaged Explorer frontend and restored browser components."""

import importlib.resources


def test_static_frontend_uses_packaged_assets_and_live_api() -> None:
    frontend = importlib.resources.files("uptimely.explorer").joinpath("app", "static")
    index = frontend.joinpath("index.html").read_text(encoding="utf-8")
    config = frontend.joinpath("config.js").read_text(encoding="utf-8")
    application = frontend.joinpath("js", "application")
    script = application.joinpath("bootstrap.js").read_text(encoding="utf-8")
    assets = application.joinpath("asset_loader.js").read_text(encoding="utf-8")
    router = application.joinpath("history_router.js").read_text(encoding="utf-8")
    explorer = application.joinpath("explorer_application.js").read_text(encoding="utf-8")
    views = application.joinpath("view_controller.js").read_text(encoding="utf-8")
    engine_pages = frontend.joinpath("js", "engine_pages.js").read_text(encoding="utf-8")
    navigation = frontend.joinpath("js", "rendering", "shared_markup.js").read_text(
        encoding="utf-8"
    )

    assert 'src="./config.js"' in index
    assert 'src="./js/application/bootstrap.js"' in index
    assert 'src="./js/theme/tailwind_theme.js"' in index
    assert 'dataUrl: "/api/explorer"' in config
    assert 'class="with-navigation bg-slate-950"' in index
    assert "tailwindcss.com/3.4.17" in index
    assert 'import { Explorer } from "./explorer_application.js"' in script
    assert "force-graph@1.52.0" in assets
    assert "3d-force-graph@1.77.0" in assets
    assert "hashchange" in router
    assert "textContent" in explorer
    assert "Loading Explorer data" in index
    assert "fetchData(configuration.dataUrl" in explorer
    assert "data/explorer.json" not in explorer
    assert '["logs", "Log", "logs"]' in navigation
    assert "logs: {" in views
    assert "export function logsPage" in engine_pages
    assert "export function infoPage" in engine_pages
    assert "engine-log-gutter" in engine_pages
    assert "engine-log-level" in engine_pages
    assert "engine-log-editor" in engine_pages


def test_original_ui_components_are_packaged_with_the_static_frontend() -> None:
    frontend = importlib.resources.files("uptimely.explorer").joinpath("app", "static")
    for name in ("base", "icons", "dashboard", "spec", "lineage", "data_lineage", "engine"):
        assert frontend.joinpath("css", f"{name}.css").is_file()
    for name in (
        "application/bootstrap",
        "application/asset_loader",
        "application/history_router",
        "application/explorer_application",
        "application/view_controller",
        "engine_pages",
        "rendering/shared_markup",
        "rendering/page_renderer",
        "catalogs/catalog_renderer",
        "catalogs/catalog_navigation",
        "catalogs/function_highlighting",
        "navigation/sidebar_controls",
        "navigation/mobile_context",
        "theme/tailwind_theme",
        "lineage/feature_lineage",
        "lineage/invocation_lineage",
        "lineage/invocation_layout",
        "lineage/lineage_components",
        "lineage/lineage_config",
        "lineage/lineage_layout",
        "lineage/lineage_view_controller",
        "animation/animation_renderer",
        "animation/playback_controller",
        "animation/table_frames",
        "animation/connection_renderer",
        "animation/viewport_controller",
    ):
        assert frontend.joinpath("js", f"{name}.js").is_file()
