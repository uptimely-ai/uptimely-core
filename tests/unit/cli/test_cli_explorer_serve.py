"""Tests for the local analytics explorer static-file server."""

import asyncio
import logging
import pathlib

import pytest
from starlette.types import ASGIApp, Message, Scope

from uptimely.cli import explorer
from uptimely.explorer import server as explorer_server


def _get(app: ASGIApp, path: str) -> tuple[int, bytes]:
    async def request() -> tuple[int, bytes]:
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
        status = next(
            message["status"] for message in messages if message["type"] == "http.response.start"
        )
        body = b"".join(
            message.get("body", b"")
            for message in messages
            if message["type"] == "http.response.body"
        )
        return status, body

    return asyncio.run(request())


def test_serve_explorer_uses_uvicorn_for_saved_static_website(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    directory = tmp_path / "website"
    directory.mkdir()
    (directory / "index.html").write_text("<h1>Spec</h1>", encoding="utf-8")
    (directory / "data_lineage.html").write_text("<h1>Data lineage</h1>", encoding="utf-8")
    (tmp_path / "private.txt").write_text("not public", encoding="utf-8")
    calls: list[tuple[str, int]] = []
    cwd = pathlib.Path.cwd()

    def run(app: ASGIApp, host: str, port: int) -> None:
        calls.append((host, port))
        assert _get(app, "/") == (200, b"<h1>Spec</h1>")
        assert _get(app, "/data_lineage.html") == (200, b"<h1>Data lineage</h1>")
        assert _get(app, "/../private.txt")[0] == 404
        raise KeyboardInterrupt

    monkeypatch.setattr(explorer_server.uvicorn, "run", run)
    caplog.set_level(logging.INFO, logger="uptimely.explorer.server")

    explorer.serve_explorer(directory, port=0, scope="selected features: pressure")

    assert pathlib.Path.cwd() == cwd
    assert calls == [("127.0.0.1", 0)]
    assert "http://127.0.0.1:0/" not in caplog.text
    assert "build scope: selected features: pressure" in caplog.text
    assert "Spec explorer server stopped." in caplog.text


@pytest.mark.parametrize("kind", ["missing", "file", "empty"])
def test_serve_explorer_rejects_missing_index(tmp_path: pathlib.Path, kind: str) -> None:
    directory = tmp_path / "website"
    if kind == "file":
        directory.write_text("not a directory", encoding="utf-8")
    elif kind == "empty":
        directory.mkdir()

    with pytest.raises((NotADirectoryError, FileNotFoundError)):
        explorer.serve_explorer(directory, port=0)


def test_serve_explorer_propagates_server_errors(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "index.html").write_text("index", encoding="utf-8")

    def fail(*args: object, **kwargs: object) -> None:
        raise OSError("address already in use")

    monkeypatch.setattr(explorer_server.uvicorn, "run", fail)

    with pytest.raises(OSError, match="address already in use"):
        explorer.serve_explorer(tmp_path, port=8001)
