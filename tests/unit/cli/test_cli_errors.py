import json
import pathlib
import sys

import pytest
from support import examples as example_support

from uptimely import application as application_module
from uptimely import plan as execution_plan
from uptimely.cli import cli

PROJECT = example_support.EXAMPLES_ROOT


SPEC_PATH = PROJECT / "artifacts/build/spec.json"


def invoke(monkeypatch: pytest.MonkeyPatch, *arguments: str) -> None:
    monkeypatch.setattr(sys, "argv", ["uptimely", *arguments])
    cli.main()


def _copy_pump_project(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    features: tuple[str, ...] | None = None,
) -> pathlib.Path:
    project_root = tmp_path / "project"
    example_support.copy_example_project(project_root, features=features)
    (project_root.parent / "__init__.py").write_text("", encoding="utf-8")
    return project_root


def _write_empty_build(project_root: pathlib.Path) -> pathlib.Path:
    build_root = project_root / application_module.BUILD_OUTPUT_DIR
    explorer_root = build_root / "explorer"
    explorer_root.mkdir(parents=True)
    (build_root / "spec.json").write_text("{}", encoding="utf-8")
    (build_root / "execution_plan.json").write_text(
        json.dumps(
            {
                "plan_version": execution_plan.PLAN_VERSION,
                "required_backend": "polars",
                "invocations": [],
                "stages": [],
            }
        ),
        encoding="utf-8",
    )
    (explorer_root / "index.html").write_text("<html></html>", encoding="utf-8")
    manifest = application_module.BuildManifest(
        build_version=application_module.BUILD_VERSION,
        uptimely_version="0.2.0",
        features=None,
        artifacts=application_module.BuildArtifactPaths(
            spec="spec.json",
            execution_plan="execution_plan.json",
        ),
    )
    (build_root / "build.json").write_text(json.dumps(manifest.model_dump()), encoding="utf-8")
    return build_root


@pytest.mark.parametrize(
    "arguments",
    [
        ["feature-graph", "--verbose"],
        ["run", "--compile", "false"],
        ["run", "--features", "health_signal_normalized"],
        ["run", "--spec", "spec.json"],
        ["run", "--plan", "plan.json"],
        ["run", "--verbose"],
        ["run", "--verbose"],
        ["run", "--log-level", "invalid"],
    ],
)
def test_workflow_argument_errors(monkeypatch: pytest.MonkeyPatch, arguments: list[str]) -> None:
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, *arguments)
    assert error.value.code == 2


@pytest.mark.parametrize(
    "command",
    [["feature-graph"], ["run"]],
)
def test_workflow_missing_inputs_are_reported(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: list[str],
) -> None:
    if command == ["run"]:
        monkeypatch.setattr(
            "uptimely.compiler.Compiler.compile",
            lambda *_args, **_kwargs: pytest.fail("Engine must not compile without a build"),
        )
        monkeypatch.setattr(
            "uptimely.engine.Engine.run",
            lambda *_args, **_kwargs: pytest.fail(
                "Engine must not execute workflows without a valid build"
            ),
        )
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, *command, "--project-root", str(tmp_path))
    assert error.value.code == 1
    result = capsys.readouterr()
    assert "ERROR    |" in result.err
    assert "uptimely build --project-root" in result.err
    if command == ["run"]:
        assert result.out == ("INFO     | Start Uptimely engine run\n")
    else:
        assert not result.out


@pytest.mark.parametrize("command", [["feature-graph"]])
@pytest.mark.usefixtures("example_projects")
def test_unknown_feature_is_reported(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], command: list[str]
) -> None:
    with pytest.raises(SystemExit) as error:
        invoke(
            monkeypatch,
            *command,
            "--spec",
            str(SPEC_PATH),
            "--features",
            "unknown_feature",
        )
    assert error.value.code == 1
    assert "unknown_feature" in capsys.readouterr().err


@pytest.mark.parametrize("content", ["not TOML", "[]", "bind = []", "unknown = true"])
def test_engine_invalid_config_is_reported(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    content: str,
) -> None:
    _write_empty_build(tmp_path)
    config = tmp_path / "config.toml"
    config.write_text(content, encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        invoke(
            monkeypatch,
            "run",
            "--project-root",
            str(tmp_path),
            "--config",
            str(config),
        )
    assert error.value.code == 1
    result = capsys.readouterr()
    assert "ERROR    |" in result.err
    assert "Engine processed" not in result.out


def test_engine_operation_failures_are_reported(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    config = tmp_path / "config.toml"
    config.write_text("[params]\n", encoding="utf-8")
    project_root = _copy_pump_project(tmp_path, monkeypatch, features=("health_signal_normalized",))
    with pytest.raises(SystemExit) as error:
        invoke(
            monkeypatch,
            "run",
            "--project-root",
            str(project_root),
            "--config",
            str(config),
            "--preview",
        )
    assert error.value.code == 1
    result = capsys.readouterr()
    assert "Engine flow failed:" in result.err
    assert "Unresolved path:" in result.err
    assert "Engine processed" not in result.out
    assert "Profile:" not in result.out


def test_engine_config_loads_backend_and_params(tmp_path: pathlib.Path) -> None:
    config = tmp_path / "uptimely.toml"
    config.write_text(
        '[engine.backend]\ndataframe = "polars"\n\n[params]\nthreshold = 10\n',
        encoding="utf-8",
    )
    settings = application_module.Uptimely(tmp_path).config
    assert settings.engine.backend.dataframe == "polars"
    assert settings.params.root == {"threshold": 10}


def test_engine_cli_uses_project_backend_config(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_empty_build(tmp_path)
    (tmp_path / "uptimely.toml").write_text(
        '[engine.backend]\ndataframe = "unsupported"\n', encoding="utf-8"
    )

    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, "run", str(tmp_path))

    assert error.value.code == 1
    assert "unsupported" in capsys.readouterr().err


@pytest.mark.parametrize("content", [None, "not JSON", '{"plan_version": "1"}'])
def test_engine_invalid_build_fails_before_execution(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    content: str | None,
) -> None:
    build_root = _write_empty_build(tmp_path)
    plan_path = build_root / "execution_plan.json"
    if content is None:
        plan_path.unlink()
    else:
        plan_path.write_text(content, encoding="utf-8")

    def fail_run(*args: object, **kwargs: object) -> None:
        pytest.fail("An invalid build must fail before workflow execution")

    monkeypatch.setattr("uptimely.engine.Engine.run", fail_run)
    with pytest.raises(SystemExit) as error:
        invoke(
            monkeypatch,
            "run",
            "--project-root",
            str(tmp_path),
        )
    assert error.value.code == 1
    result = capsys.readouterr()
    assert "ERROR    |" in result.err
    assert "uptimely build --project-root" in result.err
    expected = "INFO     | Start Uptimely engine run\n"
    if content is not None:
        expected += "INFO     | Start spec validation\nINFO     | Spec validated\n"
    assert result.out == expected


@pytest.mark.parametrize("command", [["feature-graph"]])
def test_invalid_spec_is_reported(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: list[str],
) -> None:
    spec_definition = tmp_path / "spec.json"
    spec_definition.write_text("not JSON", encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, *command, "--spec", str(spec_definition))
    assert error.value.code == 1
    result = capsys.readouterr()
    assert "ERROR    |" in result.err
    assert not result.out
