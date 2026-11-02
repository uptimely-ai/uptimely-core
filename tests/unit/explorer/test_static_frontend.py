"""Tests for the packaged, dependency-free Explorer frontend."""

import importlib.resources


def test_static_frontend_uses_packaged_assets_and_live_api() -> None:
    frontend = importlib.resources.files("uptimely.explorer").joinpath("app", "static")
    index = frontend.joinpath("index.html").read_text(encoding="utf-8")
    config = frontend.joinpath("config.js").read_text(encoding="utf-8")
    stylesheet = frontend.joinpath("css", "explorer.css").read_text(encoding="utf-8")
    script = frontend.joinpath("js", "app.js").read_text(encoding="utf-8")

    assert 'src="./config.js"' in index
    assert 'src="./js/app.js"' in index
    assert 'dataUrl: "/api/explorer"' in config
    assert "https://" not in index + config + stylesheet + script
    assert "hashchange" in script
    assert "textContent" in script
    assert "Loading Explorer data" in index
    assert "errorStatus" in script
    assert script.count("fetch(") == 1
    assert "fetch(configuration.dataUrl" in script
    assert "data/explorer.json" not in script
