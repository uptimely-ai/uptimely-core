"""Tests for serving the active Explorer build from the command line."""

import pathlib
import shutil
import sys
import threading
from urllib import request

import pytest

from uptimely import compiler, project
from uptimely.cli import cli, explorer
from uptimely.explorer import explorer as explorer_module
from uptimely.project import build as project_build

REPOSITORY_ROOT = pathlib.Path(__file__).parents[2]
SPEC_PATH = REPOSITORY_ROOT / "examples/pump_analytics/_generated/spec/spec.json"


@pytest.fixture
def built_project(tmp_path: pathlib.Path) -> pathlib.Path:
    root = tmp_path / "project with spaces"
    source = root / project.SPEC_JSON_ENTRY_FILE
    source.parent.mkdir(parents=True)
    shutil.copyfile(SPEC_PATH, source)
    project_build.build_project(root, source=source)
    return root


@pytest.mark.parametrize(
    "arguments",
    [
        ["explorer"],
        ["explorer", "unknown"],
        ["explorer", "build"],
        ["explorer", "serve", "--spec", str(SPEC_PATH)],
        ["explorer", "serve", "--plan", "plan.json"],
        ["explorer", "serve", "--directory", "website"],
        ["docs"],
    ],
)
def test_explorer_requires_valid_arguments(
    monkeypatch: pytest.MonkeyPatch, arguments: list[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["uptimely", *arguments])

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 2


@pytest.mark.parametrize("port", ["-1", "65536", "abc"])
def test_explorer_rejects_invalid_ports(monkeypatch: pytest.MonkeyPatch, port: str) -> None:
    monkeypatch.setattr(sys, "argv", ["uptimely", "explorer", "serve", "--port", port])

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 2


@pytest.mark.parametrize("bundle_state", ["missing", "incomplete"])
def test_explorer_reports_invalid_build(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    bundle_state: str,
) -> None:
    root = tmp_path / "project"
    if bundle_state == "incomplete":
        (root / project.BUILD_OUTPUT_DIR).mkdir(parents=True)
    monkeypatch.setattr(
        explorer,
        "serve_explorer",
        lambda *args: pytest.fail("Explorer must validate the build before serving"),
    )
    monkeypatch.setattr(sys, "argv", ["uptimely", "explorer", "serve", "--project-root", str(root)])

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 1
    message = capsys.readouterr().err
    assert "uptimely: error:" in message
    assert "uptimely project build --project-root" in message
    assert (
        "No active build found" in message
        if bundle_state == "missing"
        else "Active build is incomplete" in message
    )


def test_explorer_serves_saved_website_without_building_or_rendering(
    built_project: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = project.load_build_bundle(built_project)
    served: list[tuple[pathlib.Path, str, int, str]] = []
    original_serve_forever = explorer.http_server.ThreadingHTTPServer.serve_forever

    def fail(*args: object, **kwargs: object) -> None:
        pytest.fail("Serving a saved website must not compile, load source, or render")

    def serve_and_check_assets(server: explorer.http_server.ThreadingHTTPServer) -> None:
        served.append((bundle.explorer_path, "127.0.0.1", 0, "all features"))
        with (
            pytest.raises(project.BuildLockError),
            project.build_lock(built_project, exclusive=True, wait=False),
        ):
            pass
        worker = threading.Thread(
            target=original_serve_forever, args=(server,), kwargs={"poll_interval": 0.01}
        )
        worker.start()
        try:
            base_url = f"http://127.0.0.1:{server.server_port}"
            with request.urlopen(base_url, timeout=5) as response:
                assert response.status == 200
                assert b"Full build" in response.read()
            with request.urlopen(f"{base_url}/spec/overview.html", timeout=5) as response:
                assert response.status == 200
                assert response.read() == (bundle.explorer_path / "spec/overview.html").read_bytes()
        finally:
            server.shutdown()
            worker.join(timeout=5)
        assert not worker.is_alive()

    monkeypatch.setattr(project_build, "load_spec_source", fail)
    monkeypatch.setattr(compiler.Compiler, "compile", fail)
    monkeypatch.setattr(explorer_module.Explorer, "create_html", fail)
    monkeypatch.setattr(
        explorer.http_server.ThreadingHTTPServer,
        "serve_forever",
        serve_and_check_assets,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["uptimely", "explorer", "serve", "--project-root", str(built_project), "--port", "0"],
    )

    cli.main()

    assert served == [(bundle.explorer_path, "127.0.0.1", 0, "all features")]


def test_explorer_reports_selected_scope(
    built_project: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_build.build_project(built_project, features=["pump_health_score"])
    bundle = project.load_build_bundle(built_project)
    scopes: list[str] = []

    def record_scope(directory: pathlib.Path, host: str, port: int, scope: str) -> None:
        scopes.append(scope)

    monkeypatch.setattr(explorer, "serve_explorer", record_scope)
    monkeypatch.setattr(
        sys,
        "argv",
        ["uptimely", "explorer", "serve", "--project-root", str(built_project)],
    )

    cli.main()

    assert scopes == ["selected features: pump_health_score"]
    home = (bundle.explorer_path / "index.html").read_text(encoding="utf-8")
    assert "Scoped build" in home
    assert "Plan and execution: selected features: pump_health_score" in home


def test_explorer_does_not_accept_unsupported_directory_as_a_build(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "project"
    legacy_site = root / project.EXPLORER_OUTPUT_DIR
    legacy_site.mkdir(parents=True)
    (legacy_site / "index.html").write_text("legacy website", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["uptimely", "explorer", "serve", "--project-root", str(root)])

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 1
    assert "No active build found" in capsys.readouterr().err
