"""Tests for the local analytics explorer static-file server."""

import logging
import pathlib
import threading
from http import server as http_server
from urllib import error as urllib_error
from urllib import request

import pytest

from uptimely.cli import explorer


def test_serve_explorer_serves_only_the_saved_website_and_closes_on_interrupt(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    directory = tmp_path / "website"
    directory.mkdir()
    (directory / "index.html").write_text("<h1>Spec</h1>", encoding="utf-8")
    (directory / "data_lineage.html").write_text("<h1>Data lineage</h1>", encoding="utf-8")
    (tmp_path / "private.txt").write_text("not public", encoding="utf-8")
    servers: list[http_server.ThreadingHTTPServer] = []
    original_serve_forever = http_server.ThreadingHTTPServer.serve_forever
    cwd = pathlib.Path.cwd()

    def check_server(server: http_server.ThreadingHTTPServer) -> None:
        servers.append(server)
        worker = threading.Thread(
            target=original_serve_forever, args=(server,), kwargs={"poll_interval": 0.01}
        )
        worker.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            with request.urlopen(f"{base}/", timeout=5) as response:
                assert response.status == 200
                assert response.read() == b"<h1>Spec</h1>"
            with request.urlopen(f"{base}/data_lineage.html", timeout=5) as response:
                assert response.read() == b"<h1>Data lineage</h1>"
            with pytest.raises(urllib_error.HTTPError) as error:
                request.urlopen(f"{base}/../private.txt", timeout=5)
            assert error.value.code == 404
        finally:
            server.shutdown()
            worker.join(timeout=5)
        assert not worker.is_alive()
        raise KeyboardInterrupt

    monkeypatch.setattr(http_server.ThreadingHTTPServer, "serve_forever", check_server)

    caplog.set_level(logging.INFO, logger="uptimely.cli.explorer")
    explorer.serve_explorer(directory, port=0, scope="selected features: pressure")

    assert pathlib.Path.cwd() == cwd
    assert servers[0].socket.fileno() == -1
    assert f"http://127.0.0.1:{servers[0].server_port}/" in caplog.text
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


def test_serve_explorer_reports_occupied_port(tmp_path: pathlib.Path) -> None:
    (tmp_path / "index.html").write_text("index", encoding="utf-8")
    with (
        http_server.ThreadingHTTPServer(
            ("127.0.0.1", 0), http_server.SimpleHTTPRequestHandler
        ) as occupied,
        pytest.raises(OSError),
    ):
        explorer.serve_explorer(tmp_path, port=occupied.server_port)
