"""Tests for serving the active Explorer build from the command line."""

import json
import pathlib
import sys
import zipfile

import pytest
from starlette.types import ASGIApp
from support import examples as example_support

from uptimely import compiler, project
from uptimely.cli import cli, explorer
from uptimely.explorer import server as explorer_server

REPOSITORY_ROOT = pathlib.Path(__file__).parents[3]
SPEC_PATH = example_support.EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json"


@pytest.fixture
def built_project(
    tmp_path: pathlib.Path, example_project_factory: example_support.ProjectFactory
) -> pathlib.Path:
    root = tmp_path / "project with spaces"
    return example_project_factory(root)


@pytest.mark.parametrize(
    "arguments",
    [
        ["explorer"],
        ["explorer", "unknown"],
        ["explorer", "build"],
        ["explorer", "serve", "--spec", str(SPEC_PATH)],
        ["explorer", "serve", "--plan", "plan.json"],
        ["explorer", "serve", "--directory", "website"],
        ["explorer", "export"],
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
    assert "ERROR    |" in message
    assert "uptimely project build --project-root" in message
    assert (
        "No active build found" in message
        if bundle_state == "missing"
        else "Active build is incomplete" in message
    )


def test_explorer_serves_packaged_frontend_without_building(
    built_project: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project.load_build_bundle(built_project)
    served: list[tuple[pathlib.Path, str, int, str]] = []

    def fail(*args: object, **kwargs: object) -> None:
        pytest.fail("Serving the saved Explorer must not compile or load source")

    def serve_and_check_assets(app: ASGIApp, host: str, port: int) -> None:
        served.append((built_project, "127.0.0.1", 0, "all features"))
        static_root = pathlib.Path(explorer_server.__file__).parent / "app" / "static"
        assert app.routes[-1].app.directory == str(static_root)
        with project.build_lock(built_project, exclusive=True, wait=False):
            pass
        assert host == "127.0.0.1"
        assert port == 0

    monkeypatch.setattr(project, "load_spec_source", fail)
    monkeypatch.setattr(compiler.Compiler, "compile", fail)
    monkeypatch.setattr(explorer_server.uvicorn, "run", serve_and_check_assets)
    monkeypatch.setattr(
        sys,
        "argv",
        ["uptimely", "explorer", "serve", "--project-root", str(built_project), "--port", "0"],
    )

    cli.main()

    assert served == [(built_project, "127.0.0.1", 0, "all features")]


def test_explorer_reports_selected_scope(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    example_project_factory: example_support.ProjectFactory,
) -> None:
    built_project = example_project_factory(
        tmp_path / "project with spaces", features=("pump_health_score",)
    )
    project.load_build_bundle(built_project)
    scopes: list[str] = []

    def record_scope(directory: pathlib.Path, host: str, port: int, scope: str) -> None:
        scopes.append(scope)

    monkeypatch.setattr(explorer, "serve_explorer", record_scope)
    monkeypatch.setattr(
        sys,
        "argv",
        ["uptimely", "explore", str(built_project)],
    )

    cli.main()

    assert scopes == ["selected features: pump_health_score"]
    snapshot = json.loads((built_project / project.EXPLORER_DATA_FILE).read_text(encoding="utf-8"))
    assert snapshot["scope"]["label"] == "selected features: pump_health_score"


@pytest.mark.parametrize("as_zip", [False, True])
def test_explorer_export_command_creates_static_output(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    built_project: pathlib.Path,
    as_zip: bool,
) -> None:
    output = tmp_path / "export.zip" if as_zip else tmp_path / "nested" / "static"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "uptimely",
            "explorer",
            "export",
            "--project-root",
            str(built_project),
            "--output",
            str(output),
        ],
    )

    cli.main()

    if as_zip:
        with zipfile.ZipFile(output) as archive:
            config = archive.read("config.js").decode("utf-8")
            assert '"./data/explorer.json"' in config
            assert "data/explorer.json" in archive.namelist()
    else:
        assert (output / "index.html").is_file()
        config = (output / "config.js").read_text(encoding="utf-8")
        assert '"./data/explorer.json"' in config
        assert (output / "data" / "explorer.json").is_file()


@pytest.mark.parametrize("command", ["explore", "explorer"])
def test_explorer_build_option_builds_before_serving(
    built_project: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    command: str,
) -> None:
    events: list[str] = []

    def build(root: pathlib.Path) -> project.BuildBundle:
        events.append("build")
        assert root == built_project
        return project.load_build_bundle(root)

    def serve(*args: object) -> None:
        events.append("serve")

    monkeypatch.setattr(project, "build", build)
    monkeypatch.setattr(explorer, "serve_explorer", serve)
    arguments = (
        ["explorer", "serve", str(built_project)]
        if command == "explorer"
        else ["explore", str(built_project)]
    )
    monkeypatch.setattr(sys, "argv", ["uptimely", *arguments, "--build"])

    cli.main()

    assert events == ["build", "serve"]


def test_explorer_build_failure_does_not_serve(
    built_project: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_build(root: pathlib.Path) -> project.BuildBundle:
        raise project.ProjectBuildError("generation", "invalid source")

    monkeypatch.setattr(project, "build", fail_build)
    monkeypatch.setattr(
        explorer,
        "serve_explorer",
        lambda *args: pytest.fail("Explorer must not start after a failed build"),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["uptimely", "explore", str(built_project), "--build"],
    )

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 1
    assert "Project build generation failed: invalid source" in capsys.readouterr().err
