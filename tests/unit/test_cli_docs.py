"""Tests for building analytics documentation from the command line."""

import json
import pathlib
import subprocess
import sys

import jinja2
import pytest

from uptimely.cli import cli

REPOSITORY_ROOT = pathlib.Path(__file__).parents[2]
SPEC_PATH = REPOSITORY_ROOT / "examples/example_1/_generated/spec/spec.json"
PAGES = {
    "index.html",
    "spec/overview.html",
    "spec/features.html",
    "spec/entities.html",
    "spec/datasets.html",
    "spec/dimensions.html",
    "spec/functions.html",
    "spec/graph.html",
    "plan/overview.html",
    "plan/graph.html",
    "plan/stages.html",
    "execution/data_lineage.html",
}


def test_docs_build_defaults(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["uptimely", "docs", "build", "--spec", str(SPEC_PATH)])

    cli.main()

    output = tmp_path / "_generated/docs"
    assert {p.relative_to(output).as_posix() for p in output.rglob("*.html")} == PAGES
    result = capsys.readouterr()
    assert "Documentation website built at _generated/docs/index.html" in result.out
    assert not result.err


def test_docs_build_custom_output_and_timestamp(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "public/analytics"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "uptimely",
            "docs",
            "build",
            "--spec",
            str(SPEC_PATH),
            "--output",
            str(output),
            "--include-generated-at",
        ],
    )

    cli.main()

    assert {p.relative_to(output).as_posix() for p in output.rglob("*.html")} == PAGES
    assert "generated 20" in (output / "spec/overview.html").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "arguments",
    [
        ["docs"],
        ["docs", "unknown"],
        ["docs", "build"],
        ["docs", "build", "--unknown"],
        ["docs", "generate", "--spec", str(SPEC_PATH)],
    ],
)
def test_docs_requires_valid_arguments(
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
        ValueError("Invalid specification"),
        ModuleNotFoundError("Missing function module"),
        AttributeError("Missing function"),
        TypeError("Invalid callable signature"),
        jinja2.TemplateError("Invalid HTML template"),
    ],
)
def test_docs_build_errors_are_reported(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], failure: Exception
) -> None:
    def fail(*args: object, **kwargs: object) -> pathlib.Path:
        raise failure

    monkeypatch.setattr(cli, "build_docs", fail)
    monkeypatch.setattr(sys, "argv", ["uptimely", "docs", "build", "--spec", "spec.json"])

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 1
    result = capsys.readouterr()
    assert not result.out
    assert f"uptimely: error: {failure}" in result.err


@pytest.mark.parametrize("content", [None, "not JSON", '{"version": "unsupported"}'])
def test_docs_rejects_missing_or_invalid_specification(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    content: str | None,
) -> None:
    specification = tmp_path / "spec.json"
    if content is not None:
        specification.write_text(content, encoding="utf-8")
    output = tmp_path / "site"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "uptimely",
            "docs",
            "build",
            "--spec",
            str(specification),
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
def test_docs_build_imports_project_functions_in_fresh_process(
    tmp_path: pathlib.Path, explicit_project_root: bool
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "analytics_functions.py").write_text(
        "def read_values() -> object:\n    raise RuntimeError('Must not execute analytics')\n",
        encoding="utf-8",
    )
    specification = project / "spec.json"
    specification.write_text(
        json.dumps(
            {
                "version": "0.1.0",
                "functions": {
                    "read": {"read_values": {"entrypoint": "analytics_functions:read_values"}}
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
    output = tmp_path / "website"
    arguments = [
        sys.executable,
        "-m",
        "uptimely.cli.cli",
        "docs",
        "build",
        "--spec",
        str(specification),
        "--output",
        str(output),
    ]
    if explicit_project_root:
        arguments.extend(["--project-root", str(project)])

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
    assert "Documentation website built at" in result.stdout
