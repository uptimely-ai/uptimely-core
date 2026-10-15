"""Tests for building the analytics explorer from the command line."""

import json
import pathlib
import subprocess
import sys

import jinja2
import pytest

from uptimely.cli import cli, explorer

REPOSITORY_ROOT = pathlib.Path(__file__).parents[2]
ANALYTICS_PATH = REPOSITORY_ROOT / "examples/pump_analytics/_generated/analytics/analytics.json"
PAGES = {
    "index.html",
    "analytics/overview.html",
    "analytics/features.html",
    "analytics/entities.html",
    "analytics/datasets.html",
    "analytics/dimensions.html",
    "analytics/functions.html",
    "analytics/graph.html",
    "plan/overview.html",
    "plan/graph.html",
    "plan/stages.html",
    "execution/data_lineage.html",
}


def test_explorer_build_defaults(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys, "argv", ["uptimely", "explorer", "build", "--analytics", str(ANALYTICS_PATH)]
    )

    cli.main()

    output = tmp_path / "_generated/explorer"
    assert {p.relative_to(output).as_posix() for p in output.rglob("*.html")} == PAGES
    result = capsys.readouterr()
    assert "Analytics explorer built at _generated/explorer/index.html" in result.out
    assert not result.err


def test_explorer_build_custom_output_and_timestamp(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "public/analytics"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "uptimely",
            "explorer",
            "build",
            "--analytics",
            str(ANALYTICS_PATH),
            "--output",
            str(output),
            "--include-generated-at",
        ],
    )

    cli.main()

    assert {p.relative_to(output).as_posix() for p in output.rglob("*.html")} == PAGES
    assert "generated 20" in (output / "analytics/overview.html").read_text(encoding="utf-8")


def test_explorer_build_defaults_paths_from_project_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    calls: list[tuple[pathlib.Path, pathlib.Path, pathlib.Path]] = []
    monkeypatch.setattr(
        explorer,
        "build_explorer",
        lambda analytics_definition, output, project_root, include_generated_at=False: (
            calls.append((analytics_definition, output, project_root)) or output / "index.html"
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["uptimely", "explorer", "build", "--project-root", str(tmp_path)],
    )

    cli.main()

    assert calls == [
        (
            tmp_path / "_generated/analytics/analytics.json",
            tmp_path / "_generated/explorer",
            tmp_path,
        )
    ]


@pytest.mark.parametrize(
    "arguments",
    [
        ["explorer"],
        ["explorer", "unknown"],
        ["explorer", "build"],
        ["explorer", "build", "--unknown"],
        ["explorer", "generate", "--analytics", str(ANALYTICS_PATH)],
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


@pytest.mark.parametrize(
    "failure",
    [
        PermissionError("Cannot write website"),
        ValueError("Invalid analytics"),
        ModuleNotFoundError("Missing function module"),
        AttributeError("Missing function"),
        TypeError("Invalid callable signature"),
        jinja2.TemplateError("Invalid HTML template"),
    ],
)
def test_explorer_build_errors_are_reported(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], failure: Exception
) -> None:
    def fail(*args: object, **kwargs: object) -> pathlib.Path:
        raise failure

    monkeypatch.setattr(explorer, "build_explorer", fail)
    monkeypatch.setattr(
        sys, "argv", ["uptimely", "explorer", "build", "--analytics", "analytics.json"]
    )

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 1
    result = capsys.readouterr()
    assert not result.out
    assert f"uptimely: error: {failure}" in result.err


@pytest.mark.parametrize("content", [None, "not JSON", '{"version": "unsupported"}'])
def test_explorer_rejects_missing_or_invalid_analytics(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    content: str | None,
) -> None:
    analytics_definition = tmp_path / "analytics.json"
    if content is not None:
        analytics_definition.write_text(content, encoding="utf-8")
    output = tmp_path / "site"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "uptimely",
            "explorer",
            "build",
            "--analytics",
            str(analytics_definition),
            "--output",
            str(output),
        ],
    )

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 1
    assert "uptimely: error:" in capsys.readouterr().err
    assert not output.exists()


@pytest.mark.parametrize("explicit_project_root", [False, True])
def test_explorer_build_imports_project_functions_in_fresh_process(
    tmp_path: pathlib.Path, explicit_project_root: bool
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    generated = project / "_generated"
    (generated / "analytics").mkdir(parents=True)
    (project / "analytics_functions.py").write_text(
        "from __future__ import annotations\n\n"
        "import polars\n\n"
        "def read_values() -> polars.DataFrame:\n"
        "    raise RuntimeError('Must not execute analytics')\n",
        encoding="utf-8",
    )
    analytics_definition = (
        generated / "analytics/analytics.json"
        if explicit_project_root
        else project / "analytics.json"
    )
    analytics_definition.write_text(
        json.dumps(
            {
                "version": "0.2.0",
                "functions": {
                    "read_values": {
                        "operation": "read",
                        "returns": "dataframe",
                        "entrypoint": "analytics_functions:read_values",
                    }
                },
                "entities": {
                    "sample": {
                        "name": "Sample",
                        "datasets": [
                            {
                                "id": "sample_dataset",
                                "features": {"value": {"type": "float"}},
                                "mappings": {
                                    "values": {
                                        "binding": {"function": "read_values"},
                                        "features": {"inputs": [], "outputs": ["$features.value"]},
                                    }
                                },
                            }
                        ],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    output = generated / "explorer" if explicit_project_root else tmp_path / "website"
    arguments = [
        sys.executable,
        "-m",
        "uptimely.cli.cli",
        "explorer",
        "build",
    ]
    if explicit_project_root:
        arguments.extend(["--project-root", str(project)])
    else:
        arguments.extend(["--analytics", str(analytics_definition), "--output", str(output)])

    result = subprocess.run(
        arguments,
        cwd=tmp_path if explicit_project_root else project,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert {path.relative_to(output).as_posix() for path in output.rglob("*.html")} == PAGES
    assert "Analytics explorer built at" in result.stdout
