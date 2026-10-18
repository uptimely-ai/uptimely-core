"""Tests for spec, plan, and engine command groups."""

import json
import pathlib
import shutil
import subprocess
import sys

import pytest
from conftest import EXAMPLES_ROOT

from uptimely import project as project_module
from uptimely.cli import cli, engine

PROJECT = EXAMPLES_ROOT / "pump_analytics"
SPEC_PATH = PROJECT / "_generated/build/spec.json"


def invoke(monkeypatch: pytest.MonkeyPatch, *arguments: str) -> None:
    monkeypatch.setattr(sys, "argv", ["uptimely", *arguments])
    cli.main()


def _copy_pump_project(tmp_path: pathlib.Path) -> pathlib.Path:
    project_root = tmp_path / "examples" / "pump_analytics"
    shutil.copytree(PROJECT, project_root, ignore=shutil.ignore_patterns("_generated"))
    (project_root.parent / "__init__.py").write_text("", encoding="utf-8")
    return project_root


def test_feature_graph_summary_subset_and_tree(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "uptimely.compiler.Compiler.compile",
        lambda *_args, **_kwargs: pytest.fail("Feature graph inspection must not compile"),
    )
    invoke(
        monkeypatch,
        "spec",
        "feature-graph",
        "--project-root",
        str(PROJECT),
        "--features",
        "health_signal_normalized",
        "--verbose",
    )
    text = capsys.readouterr().out
    assert "Feature graph: 11 features" in text
    assert "Selected feature subset: 2 features" in text
    assert "health_signal_normalized" in text
    assert "Selected feature subset\n" in text


def test_engine_run_consumes_scoped_build_without_compiling(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project_root = _copy_pump_project(tmp_path)
    project_module.build_project(project_root, features=["health_signal_normalized"])

    def fail_compile(*args: object, **kwargs: object) -> None:
        pytest.fail("Engine execution must not compile")

    monkeypatch.setattr("uptimely.compiler.Compiler.compile", fail_compile)
    invoke(monkeypatch, "engine", "run", "--project-root", str(project_root), "--verbose")
    text = capsys.readouterr().out
    assert "Engine completed the flow" in text
    assert "Build scope: selected features: health_signal_normalized" in text
    assert "3 callables" in text
    assert "Calculated features: health_signal_normalized" in text
    assert "Execution stages" in text
    assert "Dataset(pump, pump_dataset): 5 features" in text


@pytest.mark.parametrize(
    "arguments",
    [
        ["spec"],
        ["spec"],
        ["plan"],
        ["engine"],
        ["spec", "unknown"],
        ["plan", "unknown"],
        ["engine", "unknown"],
        ["engine", "run", "--compile", "false"],
        ["engine", "run", "--features", "health_signal_normalized"],
        ["engine", "run", "--spec", "spec.json"],
        ["engine", "run", "--plan", "plan.json"],
    ],
)
def test_workflow_argument_errors(monkeypatch: pytest.MonkeyPatch, arguments: list[str]) -> None:
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, *arguments)
    assert error.value.code == 2


@pytest.mark.parametrize(
    "command",
    [["spec", "feature-graph"], ["engine", "run"]],
)
def test_workflow_missing_inputs_are_reported(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: list[str],
) -> None:
    if command == ["engine", "run"]:
        monkeypatch.setattr(
            "uptimely.compiler.Compiler.compile",
            lambda *_args, **_kwargs: pytest.fail("Engine must not compile without a build"),
        )
        monkeypatch.setattr(
            "uptimely.engine.Engine.execute",
            lambda *_args, **_kwargs: pytest.fail(
                "Engine must not execute workflows without a valid build"
            ),
        )
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, *command, "--project-root", str(tmp_path))
    assert error.value.code == 1
    result = capsys.readouterr()
    assert "uptimely: error:" in result.err
    assert "uptimely project build --project-root" in result.err
    assert not result.out


@pytest.mark.parametrize("command", [["spec", "feature-graph"]])
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


@pytest.mark.parametrize("content", ["not JSON", "[]", '{"bind": []}', '{"unknown": true}'])
def test_engine_invalid_config_is_reported(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    content: str,
) -> None:
    _write_empty_build(tmp_path)
    config = tmp_path / "engine.json"
    config.write_text(content, encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        invoke(
            monkeypatch,
            "engine",
            "run",
            "--project-root",
            str(tmp_path),
            "--config",
            str(config),
        )
    assert error.value.code == 1
    result = capsys.readouterr()
    assert "uptimely: error:" in result.err
    assert "Engine completed" not in result.out


def test_engine_operation_failures_are_reported(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    config = tmp_path / "engine.json"
    config.write_text("{}", encoding="utf-8")
    project_root = _copy_pump_project(tmp_path)
    project_module.build_project(project_root, features=["health_signal_normalized"])
    with pytest.raises(SystemExit) as error:
        invoke(
            monkeypatch,
            "engine",
            "run",
            "--project-root",
            str(project_root),
            "--config",
            str(config),
        )
    assert error.value.code == 1
    result = capsys.readouterr()
    assert "Engine flow failed:" in result.err
    assert "Unknown runtime namespace: storage" in result.err
    assert "Engine completed" not in result.out


def test_engine_settings_load_backend_and_bindings() -> None:
    settings = engine.EngineSettings.model_validate_json(
        '{"backend": {"dataframe": "polars"}, "bind": {"storage": {"source": {"path": "x"}}}}'
    )
    assert settings.backend.dataframe == "polars"
    assert settings.bind == {"storage": {"source": {"path": "x"}}}


def _write_empty_build(project_root: pathlib.Path) -> pathlib.Path:
    build_root = project_root / project_module.BUILD_OUTPUT_DIR
    explorer_root = build_root / "explorer"
    explorer_root.mkdir(parents=True)
    (build_root / "spec.json").write_text("{}", encoding="utf-8")
    (build_root / "execution_plan.json").write_text(
        json.dumps(
            {
                "plan_version": "0.2.0",
                "required_backend": "polars",
                "resources": {},
                "callables": [],
                "stages": [],
            }
        ),
        encoding="utf-8",
    )
    (explorer_root / "index.html").write_text("<html></html>", encoding="utf-8")
    manifest = project_module.BuildManifest(
        schema_version=project_module.BUILD_SCHEMA_VERSION,
        uptimely_version="0.2.0",
        features=None,
        artifacts=project_module.BuildArtifactPaths(
            spec="spec.json",
            execution_plan="execution_plan.json",
            explorer="explorer",
        ),
        explorer_files=["index.html"],
    )
    (build_root / "build.json").write_text(json.dumps(manifest.model_dump()), encoding="utf-8")
    return build_root


@pytest.mark.parametrize("content", [None, "not JSON", '{"plan_version": "unsupported"}'])
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

    def fail_execute(*args: object, **kwargs: object) -> None:
        pytest.fail("An invalid build must fail before workflow execution")

    monkeypatch.setattr("uptimely.engine.Engine.execute", fail_execute)
    with pytest.raises(SystemExit) as error:
        invoke(
            monkeypatch,
            "engine",
            "run",
            "--project-root",
            str(tmp_path),
        )
    assert error.value.code == 1
    result = capsys.readouterr()
    assert "uptimely: error:" in result.err
    assert "uptimely project build --project-root" in result.err
    assert not result.out


@pytest.mark.parametrize("command", [["spec", "feature-graph"]])
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
    assert "uptimely: error:" in result.err
    assert not result.out


def test_workflows_import_project_functions_in_fresh_process(tmp_path: pathlib.Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "cli_project_functions.py").write_text(
        "import polars\n"
        "def read_values(path: str) -> polars.DataFrame:\n"
        "    return polars.read_json(path)\n",
        encoding="utf-8",
    )
    data = project / "data.json"
    data.write_text('[{"value": 1.0}]', encoding="utf-8")
    config = project / "config" / "engine.json"
    config.parent.mkdir()
    config.write_text(
        json.dumps({"bind": {"storage": {"source": {"path": str(data)}}}}), encoding="utf-8"
    )
    spec_path = project / "config" / "spec.json"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        json.dumps(
            {
                "version": "0.2.0",
                "functions": {
                    "read_values": {
                        "operation": "read",
                        "returns": "dataframe",
                        "entrypoint": "cli_project_functions:read_values",
                        "args": {"path": {"type": "string"}},
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
                                        "binding": {
                                            "function": "read_values",
                                            "args": {"path": "?storage.source.path"},
                                        },
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
    project_module.build_project(project, source=spec_path)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "uptimely.cli.cli",
            "engine",
            "run",
            "--verbose",
            "--project-root",
            str(project),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Build scope: all features" in result.stdout
    assert "read_values(sample) -> value" in result.stdout
    assert (project / "_generated/build/execution_plan.json").is_file()
