"""Tests for the packaged Explorer frontend and snapshot API."""

import asyncio
import io
import json
import logging
import pathlib
import urllib.parse
import zipfile

import polars as pl
import pytest
from starlette.types import ASGIApp, Message, Scope

from uptimely import engine, project, spec
from uptimely import plan as execution_plan
from uptimely.cli import explorer
from uptimely.explorer import server as explorer_server
from uptimely.run import store as run_store


def _snapshot(name: str = "Example project") -> dict[str, object]:
    return {
        "format_version": 1,
        "project": {"name": name, "spec_version": 3},
        "scope": {"label": "all features", "features": None, "is_scoped": False},
        "catalogs": {
            "configuration": {},
            "summary": {},
            "feature_dependencies": [],
            "function_groups": {},
        },
        "graphs": {
            "feature_lineage": {"nodes": [], "links": []},
            "feature_style": {},
            "invocation_lineage": {"nodes": [], "links": []},
            "invocation_style": {},
        },
        "plan": {"stage_count": 0, "invocation_count": 0},
        "stages": [],
        "animation": {"stages": []},
    }


def _get(app: ASGIApp, path: str) -> tuple[int, bytes, dict[str, str]]:
    async def request() -> tuple[int, bytes, dict[str, str]]:
        messages: list[Message] = []
        request_sent = False

        async def receive() -> Message:
            nonlocal request_sent
            if request_sent:
                return {"type": "http.disconnect"}
            request_sent = True
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message: Message) -> None:
            messages.append(message)

        url = urllib.parse.urlsplit(path)
        scope: Scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": url.path,
            "raw_path": url.path.encode(),
            "query_string": url.query.encode(),
            "root_path": "",
            "headers": [],
            "client": ("127.0.0.1", 1234),
            "server": ("127.0.0.1", 8001),
        }
        await app(scope, receive, send)
        start = next(message for message in messages if message["type"] == "http.response.start")
        status = start["status"]
        headers = {key.decode().lower(): value.decode() for key, value in start.get("headers", [])}
        body = b"".join(
            message.get("body", b"")
            for message in messages
            if message["type"] == "http.response.body"
        )
        return status, body, headers

    return asyncio.run(request())


def _saved_run(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> engine.Engine:
    source = tmp_path / "spec.json"
    spec.write_document(spec.Spec(), source)
    bundle = project.build_project(tmp_path, json_spec=source)
    runtime = engine.Engine(bundle, engine.EngineConfig())

    def execute(**kwargs: object) -> engine.ExecutionResult:
        logging.getLogger("uptimely.engine").warning("saved message")
        return engine.ExecutionResult(
            datasets={"sample": pl.DataFrame({"value": [1, 2, 3]})},
            calculated_outputs={},
            invocation_statuses={},
            durations={},
            failures={},
            plan_version=execution_plan.PLAN_VERSION,
        )

    monkeypatch.setattr(runtime, "_execute", execute)
    runtime.run(preview_rows=2)
    return runtime


@pytest.mark.parametrize("path", ["/", "/css/spec.css", "/js/catalogs/catalog_renderer.js"])
def test_frontend_assets_require_cache_revalidation(tmp_path: pathlib.Path, path: str) -> None:
    app = explorer_server.create_app(tmp_path)
    status, body, headers = _get(app, path)
    assert status == 200
    assert body
    assert headers["cache-control"] == "no-cache"
    assert "etag" in headers


def test_run_api_reads_fresh_metadata_previews_and_logs(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = explorer_server.create_app(tmp_path)
    assert _get(app, "/api/run")[0] == 404
    runtime = _saved_run(tmp_path, monkeypatch)

    status, body, headers = _get(app, "/api/run")
    assert status == 200
    assert headers["cache-control"] == "no-store"
    manifest = json.loads(body)
    run_id = manifest["run_id"]
    assert manifest["status"] == "succeeded"
    assert "format_version" not in manifest

    status, body, headers = _get(app, f"/api/run/preview/sample?run_id={run_id}")
    assert status == 200
    assert headers["cache-control"] == "no-store"
    assert json.loads(body)["rows"] == [[1], [2]]
    status, body, _ = _get(app, f"/api/run/logs?run_id={run_id}&offset=0&limit=1")
    assert status == 200
    assert json.loads(body)[0]["message"] == "saved message"
    assert _get(app, "/api/run/preview/missing")[0] == 404
    for query in ("offset=-1", "limit=0", "limit=1001", "limit=invalid"):
        assert _get(app, f"/api/run/logs?{query}")[0] == 422

    runtime.run()
    assert json.loads(_get(app, "/api/run")[1])["run_id"] != run_id
    assert _get(app, f"/api/run/preview/sample?run_id={run_id}")[0] == 409
    assert _get(app, f"/api/run/logs?run_id={run_id}")[0] == 409


@pytest.mark.parametrize("artifact", ["run.json", "preview/sample.json", "log.jsonl"])
@pytest.mark.parametrize("damage", ["missing", "corrupt"])
def test_run_api_reports_invalid_or_missing_artifacts(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, artifact: str, damage: str
) -> None:
    _saved_run(tmp_path, monkeypatch)
    saved = run_store.RunStore(tmp_path)
    path = saved.root / artifact
    if damage == "missing":
        path.unlink()
    else:
        path.write_text("{", encoding="utf-8")
    endpoint = {
        "run.json": "/api/run",
        "preview/sample.json": "/api/run/preview/sample",
        "log.jsonl": "/api/run/logs",
    }[artifact]

    status, body, _ = _get(explorer_server.create_app(tmp_path), endpoint)

    assert status == (404 if artifact == "run.json" and damage == "missing" else 503)
    assert json.loads(body)["detail"]


def test_app_serves_packaged_frontend_and_reads_fresh_snapshot(tmp_path: pathlib.Path) -> None:
    snapshot_path = tmp_path / project.EXPLORER_DATA_FILE
    snapshot_path.parent.mkdir(parents=True)
    snapshot_path.write_text(json.dumps(_snapshot()), encoding="utf-8")
    app = explorer_server.create_app(tmp_path)

    status, body, _ = _get(app, "/")
    assert status == 200
    assert b"Analytics Explorer" in body
    assert _get(app, "/css/explorer.css")[0] == 200
    for path in (
        "/js/application/bootstrap.js",
        "/js/application/view_controller.js",
        "/js/catalogs/catalog_renderer.js",
        "/js/lineage/feature_lineage.js",
        "/js/animation/playback_controller.js",
        "/js/rendering/shared_markup.js",
        "/js/navigation/sidebar_controls.js",
        "/js/theme/tailwind_theme.js",
    ):
        assert _get(app, path)[0] == 200

    status, body, headers = _get(app, "/api/explorer")
    assert status == 200
    assert headers["cache-control"] == "no-store"
    assert json.loads(body)["project"]["name"] == "Example project"

    snapshot_path.write_text(json.dumps(_snapshot("Rebuilt project")), encoding="utf-8")
    assert json.loads(_get(app, "/api/explorer")[1])["project"]["name"] == "Rebuilt project"


def test_api_reads_snapshot_after_project_rebuild(tmp_path: pathlib.Path) -> None:
    project_root = tmp_path / "project"
    spec_path = project_root / "spec.json"
    definition = spec.Spec(name="Before rebuild")
    spec.write_document(definition, spec_path)
    project.build_project(project_root, json_spec=spec_path)
    app = explorer_server.create_app(project_root)

    assert json.loads(_get(app, "/api/explorer")[1])["project"]["name"] == "Before rebuild"

    definition.name = "After rebuild"
    spec.write_document(definition, spec_path)
    project.build_project(project_root, json_spec=spec_path)

    assert json.loads(_get(app, "/api/explorer")[1])["project"]["name"] == "After rebuild"


@pytest.mark.parametrize("kind", ["missing", "corrupt", "unsupported"])
def test_snapshot_api_reports_rebuild_instructions(tmp_path: pathlib.Path, kind: str) -> None:
    snapshot_path = tmp_path / project.EXPLORER_DATA_FILE
    if kind != "missing":
        snapshot_path.parent.mkdir(parents=True)
        content = "not json" if kind == "corrupt" else json.dumps({"format_version": 99})
        snapshot_path.write_text(content, encoding="utf-8")

    status, body, _ = _get(explorer_server.create_app(tmp_path), "/api/explorer")

    assert status == 503
    assert "uptimely project build" in json.loads(body)["detail"]


def test_export_route_returns_static_zip_with_relative_data_url(
    tmp_path: pathlib.Path,
) -> None:
    snapshot_path = tmp_path / project.EXPLORER_DATA_FILE
    snapshot_path.parent.mkdir(parents=True)
    snapshot_path.write_text(json.dumps(_snapshot()), encoding="utf-8")

    status, body, headers = _get(explorer_server.create_app(tmp_path), "/api/explorer/export")

    assert status == 200
    assert headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        assert json.loads(archive.read("data/explorer.json")) == _snapshot()
        assert '"./data/explorer.json"' in archive.read("config.js").decode("utf-8")


@pytest.mark.parametrize("kind", ["missing", "file"])
def test_create_app_rejects_missing_project_root(tmp_path: pathlib.Path, kind: str) -> None:
    project_root = tmp_path / "project"
    if kind == "file":
        project_root.write_text("not a directory", encoding="utf-8")

    with pytest.raises(NotADirectoryError):
        explorer_server.create_app(project_root)


def test_serve_explorer_uses_uvicorn_without_a_build_lock(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    snapshot_path = root / project.EXPLORER_DATA_FILE
    snapshot_path.parent.mkdir(parents=True)
    snapshot_path.write_text(json.dumps(_snapshot()), encoding="utf-8")
    calls: list[tuple[str, int]] = []
    cwd = pathlib.Path.cwd()

    def run(app: ASGIApp, host: str, port: int) -> None:
        calls.append((host, port))
        assert _get(app, "/")[0] == 200
        assert _get(app, "/api/explorer")[0] == 200
        with project.build_lock(root, exclusive=True, wait=False):
            pass
        raise KeyboardInterrupt

    monkeypatch.setattr(explorer_server.uvicorn, "run", run)
    caplog.set_level(logging.INFO, logger="uptimely.explorer.server")

    explorer.serve_explorer(root, port=0, scope="selected features: pressure")

    assert pathlib.Path.cwd() == cwd
    assert calls == [("127.0.0.1", 0)]
    assert "http://127.0.0.1:0/" not in caplog.text
    assert "build scope: selected features: pressure" in caplog.text
    assert "Spec explorer server stopped." in caplog.text


def test_serve_explorer_propagates_server_errors(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tmp_path.mkdir(exist_ok=True)

    def fail(*args: object, **kwargs: object) -> None:
        raise OSError("address already in use")

    monkeypatch.setattr(explorer_server.uvicorn, "run", fail)

    with pytest.raises(OSError, match="address already in use"):
        explorer.serve_explorer(tmp_path, port=8001)
