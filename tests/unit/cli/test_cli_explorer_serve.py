"""Tests for the packaged Explorer frontend and snapshot API."""

import asyncio
import json
import logging
import pathlib

import pytest
from starlette.types import ASGIApp, Message, Scope

from uptimely import project
from uptimely.cli import explorer
from uptimely.explorer import server as explorer_server


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

        scope: Scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
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


def test_app_serves_packaged_frontend_and_reads_fresh_snapshot(tmp_path: pathlib.Path) -> None:
    snapshot_path = tmp_path / project.EXPLORER_DATA_FILE
    snapshot_path.parent.mkdir(parents=True)
    snapshot_path.write_text(json.dumps(_snapshot()), encoding="utf-8")
    app = explorer_server.create_app(tmp_path)

    status, body, _ = _get(app, "/")
    assert status == 200
    assert b"Analytics Explorer" in body
    assert _get(app, "/css/explorer.css")[0] == 200
    assert _get(app, "/js/app.js")[0] == 200

    status, body, headers = _get(app, "/api/explorer")
    assert status == 200
    assert headers["cache-control"] == "no-store"
    assert json.loads(body)["project"]["name"] == "Example project"

    snapshot_path.write_text(json.dumps(_snapshot("Rebuilt project")), encoding="utf-8")
    assert json.loads(_get(app, "/api/explorer")[1])["project"]["name"] == "Rebuilt project"


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
