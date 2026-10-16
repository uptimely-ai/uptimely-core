"""Tests for the analytics command-line interface."""

import json
import pathlib
import subprocess
import sys

import pytest

from uptimely import analytics
from uptimely.cli import cli

REPOSITORY_ROOT = pathlib.Path(__file__).parents[2]
PUMP_MODULE = "examples.pump_analytics.config.analytics.analytics"


def invoke(monkeypatch: pytest.MonkeyPatch, *arguments: str) -> None:
    monkeypatch.setattr(sys, "argv", ["uptimely", "analytics", "export", *arguments])
    cli.main()


@pytest.mark.parametrize(
    ("module", "name", "entities"),
    [
        (PUMP_MODULE, "Pump analytics", {"pump", "pump_telemetry"}),
        (
            "examples.simple_analytics.config.analytics.analytics",
            "Simple analytics",
            {"simple_analytics"},
        ),
    ],
)
def test_export_example_in_fresh_process(
    tmp_path: pathlib.Path, module: str, name: str, entities: set[str]
) -> None:
    output = tmp_path / "export/analytics.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "uptimely.cli.cli",
            "analytics",
            "export",
            "--module",
            module,
            "--project-root",
            str(REPOSITORY_ROOT),
            "--output",
            str(output),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert f"Analytics written to {output}" in result.stdout
    assert not result.stderr
    analytics_definition = analytics.load_analytics(output)
    assert analytics_definition.name == name
    assert set(analytics_definition.entities) == entities
    assert analytics_definition.source.name == "python_api"
    assert analytics_definition.source.generated is True
    assert analytics_definition.functions.by_operation("read")


@pytest.mark.parametrize("explicit_root", [False, True])
def test_export_default_output_and_import_root(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    explicit_root: bool,
) -> None:
    module = f"export_default_{explicit_root}"
    (tmp_path / f"{module}.py").write_text(
        "from examples.simple_analytics.config.analytics.analytics import python_analytics\n",
        encoding="utf-8",
    )
    arguments = ["--module", module]
    if explicit_root:
        arguments.extend(["--project-root", str(tmp_path)])
    else:
        monkeypatch.chdir(tmp_path)
    invoke(monkeypatch, *arguments)
    output = tmp_path / "_generated/analytics/analytics.json"
    assert json.loads(output.read_text(encoding="utf-8"))["name"] == "Simple analytics"
    assert "Analytics written to" in capsys.readouterr().out


def test_export_explicit_output_is_relative_to_working_directory(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    invoke(
        monkeypatch,
        "--module",
        PUMP_MODULE,
        "--project-root",
        str(REPOSITORY_ROOT),
        "--output",
        "custom/analytics.json",
    )
    assert (tmp_path / "custom/analytics.json").is_file()


@pytest.mark.parametrize(
    ("module", "content", "error_text"),
    [
        ("missing_export_module", None, "No module named"),
        ("missing_export_declaration", "", "python_analytics"),
        (
            "invalid_export_declaration",
            "python_analytics = {}",
            "must be a PythonAnalytics",
        ),
        (
            "broken_export_dependency",
            "import missing_export_dependency",
            "missing_export_dependency",
        ),
        (
            "invalid_export_analytics",
            "from uptimely.analytics import python as python_analytics\n"
            "python_analytics = python_analytics.PythonAnalytics()",
            "At least one entity is required",
        ),
    ],
)
def test_export_errors_are_reported(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    module: str,
    content: str | None,
    error_text: str,
) -> None:
    if content is not None:
        (tmp_path / f"{module}.py").write_text(content, encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, "--module", module, "--project-root", str(tmp_path))
    assert error.value.code == 1
    result = capsys.readouterr()
    assert "uptimely: error:" in result.err
    assert error_text in result.err
    assert not result.out
    assert not (tmp_path / "_generated/analytics/analytics.json").exists()


def test_export_write_errors_are_reported(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "blocked"
    output.write_text("not a directory", encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, "--module", PUMP_MODULE, "--output", str(output / "analytics.json"))
    assert error.value.code == 1
    result = capsys.readouterr()
    assert "uptimely: error:" in result.err
    assert not result.out


def test_export_requires_module(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch)
    assert error.value.code == 2
