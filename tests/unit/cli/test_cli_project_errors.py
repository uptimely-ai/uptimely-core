import pathlib
import shutil
import sys

import pytest
from support import examples as example_support

from uptimely import application
from uptimely.build import builder as project_build
from uptimely.cli import cli


def invoke(monkeypatch: pytest.MonkeyPatch, *arguments: str) -> None:
    monkeypatch.setattr(sys, "argv", ["uptimely", "build", *arguments])
    cli.main()


def copy_project_spec(root: pathlib.Path) -> pathlib.Path:
    bundle = example_support.example_bundle()
    source = root / application.SPEC_JSON_ENTRY_FILE
    source.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(bundle.spec_path, source)
    return source


def test_project_build_rejects_invalid_scope(tmp_path: pathlib.Path) -> None:
    root = tmp_path / "project"
    copy_project_spec(root)

    with pytest.raises(application.ProjectBuildError, match="at least one output feature"):
        project_build.build(root, features=[])
    with pytest.raises(application.ProjectBuildError, match="Unknown output feature"):
        project_build.build(root, features=["not-a-feature"])
    assert not (root / application.BUILD_OUTPUT_DIR).exists()


def test_project_build_missing_source(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, "--project-root", str(tmp_path))
    assert error.value.code == 1
    assert "Project build source loading failed: No spec source found" in capsys.readouterr().err
    assert not (tmp_path / application.ARTIFACTS_DIR).exists()


def test_project_build_help(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["uptimely", "build", "--help"])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 0
    result = capsys.readouterr()
    assert "--python-spec MODULE:ATTRIBUTE" in result.out
    assert "--json-spec" in result.out
    assert "--project-root" in result.out
    assert "--features FEATURE" in result.out
    assert "--log-level" in result.out
    assert not result.err


@pytest.mark.parametrize(
    "arguments",
    [
        [
            "build",
            "--python-spec",
            "module:attribute",
            "--json-spec",
            "source.json",
        ],
        ["build", "--output", "custom"],
        ["build", "--features"],
        ["build", "--verbose"],
        ["build", "--verbose"],
        ["feature-graph", "--verbose"],
    ],
)
def test_project_requires_valid_arguments(
    monkeypatch: pytest.MonkeyPatch, arguments: list[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["uptimely", *arguments])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2
