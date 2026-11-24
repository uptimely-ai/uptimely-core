import pathlib
import sys

import pytest

from uptimely.cli import cli


def invoke(monkeypatch: pytest.MonkeyPatch, *arguments: str) -> None:
    monkeypatch.setattr(sys, "argv", ["uptimely", "test", *arguments])
    cli.main()


def test_default_folder_is_found_from_project_root(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project = tmp_path / "project"
    (project / "tests" / "uptimely").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, str(project))

    assert error.value.code == 1
    assert "Folder found, not implemented" in capsys.readouterr().err


@pytest.mark.parametrize("create_file", [False, True])
def test_missing_default_folder_is_reported(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    create_file: bool,
) -> None:
    monkeypatch.chdir(tmp_path)
    if create_file:
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "uptimely").write_text("", encoding="utf-8")

    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch)

    assert error.value.code == 1
    assert "Configured test folder tests/uptimely not found" in capsys.readouterr().err


@pytest.mark.parametrize("absolute", [False, True])
def test_configured_folder_is_used(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    absolute: bool,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    folder = project / "custom-tests"
    path = str(folder) if absolute else "custom-tests"
    (project / "uptimely.toml").write_text(f'[test]\npath = "{path}"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, "--project-root", str(project))
    assert error.value.code == 1
    assert f"Configured test folder {path} not found" in capsys.readouterr().err

    folder.mkdir()
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, "--project-root", str(project))
    assert error.value.code == 1
    assert "Folder found, not implemented" in capsys.readouterr().err


@pytest.mark.parametrize("config_arg", ["prod", "override.toml"])
def test_selected_config_is_used(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    config_arg: str,
) -> None:
    (tmp_path / "uptimely.toml").write_text('[test]\npath = "default"\n', encoding="utf-8")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "prod.toml").write_text('[test]\npath = "selected"\n', encoding="utf-8")
    (tmp_path / "override.toml").write_text('[test]\npath = "selected"\n', encoding="utf-8")
    (tmp_path / "selected").mkdir()
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, "--config", config_arg)

    assert error.value.code == 1
    assert "Folder found, not implemented" in capsys.readouterr().err


@pytest.mark.parametrize("path", ['""', "42"])
def test_invalid_test_path_is_reported(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    path: str,
) -> None:
    (tmp_path / "uptimely.toml").write_text(f"[test]\npath = {path}\n", encoding="utf-8")

    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, str(tmp_path))

    assert error.value.code == 1
    assert "test.path" in capsys.readouterr().err
