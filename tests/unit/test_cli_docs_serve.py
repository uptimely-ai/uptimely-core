"""Tests for the local documentation preview server."""

import sys
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from uptimely.cli import cli


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ([], (Path("_generated/docs"), "127.0.0.1", 8001)),
        (
            ["--directory", "public", "--host", "0.0.0.0", "--port", "9000"],
            (Path("public"), "0.0.0.0", 9000),
        ),
        (["--port", "0"], (Path("_generated/docs"), "127.0.0.1", 0)),
    ],
)
def test_serve_arguments(
    monkeypatch: pytest.MonkeyPatch,
    arguments: list[str],
    expected: tuple[Path, str, int],
) -> None:
    calls: list[tuple[Path, str, int]] = []
    monkeypatch.setattr(
        cli, "serve_docs", lambda directory, host, port: calls.append((directory, host, port))
    )
    monkeypatch.setattr(sys, "argv", ["uptimely", "docs", "serve", *arguments])

    cli.main()

    assert calls == [expected]


@pytest.mark.parametrize("port", ["-1", "65536", "abc"])
def test_serve_rejects_invalid_ports(monkeypatch: pytest.MonkeyPatch, port: str) -> None:
    monkeypatch.setattr(sys, "argv", ["uptimely", "docs", "serve", "--port", port])

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 2


@pytest.mark.parametrize("kind", ["missing", "file", "empty"])
def test_serve_reports_missing_website(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    kind: str,
) -> None:
    directory = tmp_path / "website"
    if kind == "file":
        directory.write_text("not a directory", encoding="utf-8")
    elif kind == "empty":
        directory.mkdir()
    monkeypatch.setattr(sys, "argv", ["uptimely", "docs", "serve", "--directory", str(directory)])

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 1
    result = capsys.readouterr()
    assert "uptimely: error:" in result.err
    assert not result.out


def test_serve_serves_only_selected_directory_and_closes_on_interrupt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    directory = tmp_path / "website"
    directory.mkdir()
    (directory / "index.html").write_text("<h1>Analytics</h1>", encoding="utf-8")
    (directory / "feature_graph.html").write_text("<h1>Graph</h1>", encoding="utf-8")
    (tmp_path / "private.txt").write_text("not public", encoding="utf-8")
    servers: list[ThreadingHTTPServer] = []
    original_serve_forever = ThreadingHTTPServer.serve_forever
    cwd = Path.cwd()

    def check_server(server: ThreadingHTTPServer) -> None:
        servers.append(server)
        worker = Thread(
            target=original_serve_forever, args=(server,), kwargs={"poll_interval": 0.01}
        )
        worker.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            with urlopen(f"{base}/", timeout=5) as response:
                assert response.status == 200
                assert response.read() == b"<h1>Analytics</h1>"
            with urlopen(f"{base}/feature_graph.html", timeout=5) as response:
                assert response.read() == b"<h1>Graph</h1>"
            with pytest.raises(HTTPError) as error:
                urlopen(f"{base}/../private.txt", timeout=5)
            assert error.value.code == 404
        finally:
            server.shutdown()
            worker.join(timeout=5)
        assert not worker.is_alive()
        raise KeyboardInterrupt

    monkeypatch.setattr(ThreadingHTTPServer, "serve_forever", check_server)

    cli.serve_docs(directory, port=0)

    assert Path.cwd() == cwd
    assert servers[0].socket.fileno() == -1
    result = capsys.readouterr()
    assert f"http://127.0.0.1:{servers[0].server_port}/" in result.out
    assert "Documentation server stopped." in result.out


def test_serve_reports_occupied_port(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "index.html").write_text("index", encoding="utf-8")
    with ThreadingHTTPServer(("127.0.0.1", 0), cli.SimpleHTTPRequestHandler) as occupied:
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "uptimely",
                "docs",
                "serve",
                "--directory",
                str(tmp_path),
                "--port",
                str(occupied.server_port),
            ],
        )
        with pytest.raises(SystemExit) as error:
            cli.main()

    assert error.value.code == 1
    assert "uptimely: error:" in capsys.readouterr().err
