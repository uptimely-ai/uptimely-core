import json
import pathlib
import sys

import pytest
from support import examples as example_support

from uptimely.cli import cli


def invoke(monkeypatch: pytest.MonkeyPatch, *arguments: str) -> None:
    monkeypatch.setattr(sys, "argv", ["uptimely", "test", *arguments])
    cli.main()


def test_default_folder_requires_saved_build(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project = tmp_path / "project"
    (project / "tests" / "uptimely").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, str(project))

    assert error.value.code == 1
    assert "build" in capsys.readouterr().err.lower()


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
    assert "build" in capsys.readouterr().err.lower()


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
    assert "build" in capsys.readouterr().err.lower()


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


def _case_project(
    tmp_path: pathlib.Path, factory: example_support.ProjectFactory
) -> tuple[pathlib.Path, pathlib.Path, dict]:
    project = factory(tmp_path / "project")
    folder = project / "cases"
    folder.mkdir()
    case_path = folder / "pump_series.json"
    suite = json.loads(
        (project / "tests" / "uptimely" / "pump_series.json").read_text(encoding="utf-8")
    )
    case_path.write_text(json.dumps(suite), encoding="utf-8")
    (project / "case-config.toml").write_text('[test]\npath = "cases"\n', encoding="utf-8")
    return project, case_path, suite


def test_test_command_uses_saved_source_and_preserves_run(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    example_project_factory: example_support.ProjectFactory,
) -> None:
    project, _, _ = _case_project(tmp_path, example_project_factory)
    (project / "src" / "pump_analytics.py").write_text(
        'raise RuntimeError("live source must not be used")\n', encoding="utf-8"
    )
    run_path = project / "artifacts" / "run"
    run_path.mkdir(parents=True, exist_ok=True)
    sentinel = run_path / "sentinel"
    sentinel.write_text("unchanged", encoding="utf-8")

    invoke(monkeypatch, str(project), "--config", str(project / "case-config.toml"))

    report = json.loads((project / "artifacts" / "test" / "test.json").read_text(encoding="utf-8"))
    assert report["status"] == "passed"
    assert report["build"]["fingerprint"]
    assert len(report["cases"]) == 1
    assert "1 passed, 0 failed" in capsys.readouterr().out
    assert sentinel.read_text(encoding="utf-8") == "unchanged"


def test_test_command_saves_failures_and_continues(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    example_project_factory: example_support.ProjectFactory,
) -> None:
    project, case_path, suite = _case_project(tmp_path, example_project_factory)
    cases = next(iter(suite.values()))["cases"]
    cases["other"] = json.loads(json.dumps(cases["basic"]))
    cases["basic"]["expected"]["return"][0]["bearing_temperature_series_max"] = 1.0
    case_path.write_text(json.dumps(suite), encoding="utf-8")

    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, str(project), "--config", str(project / "case-config.toml"))

    assert error.value.code == 1
    report = json.loads((project / "artifacts" / "test" / "test.json").read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert [case["status"] for case in report["cases"]] == ["failed", "passed"]
    assert "does not match expected" in capsys.readouterr().out


@pytest.mark.parametrize(
    "invalid", ["duplicate", "missing-input", "unknown-operator", "io", "empty"]
)
def test_invalid_cases_are_reported(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    example_project_factory: example_support.ProjectFactory,
    invalid: str,
) -> None:
    project, case_path, suite = _case_project(tmp_path, example_project_factory)
    if invalid == "duplicate":
        case_path.write_text('{"same": {}, "same": {}}', encoding="utf-8")
    elif invalid == "missing-input":
        next(iter(suite.values()))["cases"]["basic"]["inputs"] = {}
        case_path.write_text(json.dumps(suite), encoding="utf-8")
    elif invalid == "io":
        case_path.write_text(
            json.dumps({"read_pump_series": next(iter(suite.values()))}), encoding="utf-8"
        )
    elif invalid == "empty":
        case_path.write_text("{}", encoding="utf-8")
    else:
        suite["unknown"] = next(iter(suite.values()))
        case_path.write_text(json.dumps(suite), encoding="utf-8")

    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, str(project), "--config", str(project / "case-config.toml"))

    assert error.value.code == 1
    report = json.loads((project / "artifacts" / "test" / "test.json").read_text(encoding="utf-8"))
    if invalid == "missing-input":
        assert report["status"] == "failed"
        assert report["cases"][0]["status"] == "error"
        assert "dataframe inputs" in report["cases"][0]["message"]
    else:
        assert report["status"] == "error"
        expected = {
            "duplicate": "Duplicate",
            "unknown-operator": "unknown",
            "io": "I/O and workflow",
            "empty": "No test cases",
        }[invalid]
        assert expected in report["error"]
