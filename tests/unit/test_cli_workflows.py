"""Tests for analytics, plan, and engine command groups."""

import json
import pathlib
import subprocess
import sys

import pytest

from uptimely import plan as plan_module
from uptimely.cli import cli, engine, plan

PROJECT = pathlib.Path(__file__).parents[2] / "examples/pump_analytics"
ANALYTICS_PATH = PROJECT / "_generated/analytics/analytics.json"


def invoke(monkeypatch: pytest.MonkeyPatch, *arguments: str) -> None:
    monkeypatch.setattr(sys, "argv", ["uptimely", *arguments])
    cli.main()


def test_plan_build_defaults_and_verbose(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "_generated/analytics").mkdir(parents=True)
    (tmp_path / "_generated/analytics/analytics.json").write_bytes(ANALYTICS_PATH.read_bytes())
    invoke(monkeypatch, "plan", "build", "--project-root", str(tmp_path), "--verbose")

    restored = plan_module.ExecutionPlan.from_json(
        tmp_path / "_generated/compile/execution_plan.json"
    )
    assert len(restored.operations) == 13
    text = capsys.readouterr().out
    assert "Compiled 13 operations" in text
    assert "Execution stages" in text
    assert "normalize_health_signal(pump)" in text
    assert " <- [" in text


def test_plan_build_explicit_paths_and_subset(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "custom/plan.json"
    invoke(
        monkeypatch,
        "plan",
        "build",
        "--analytics",
        str(ANALYTICS_PATH),
        "--output",
        str(output),
        "--features",
        "health_signal_normalized",
    )
    restored = plan_module.ExecutionPlan.from_json(output)
    assert {operation.function_id for operation in restored.operations} == {
        "read_pump_telemetry",
        "maximum",
        "normalize_health_signal",
    }


def test_feature_graph_summary_subset_and_tree(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    invoke(
        monkeypatch,
        "analytics",
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


@pytest.mark.parametrize("compile_first", [True, False])
def test_engine_run_compile_and_saved_plan(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    compile_first: bool,
) -> None:
    arguments = ["engine", "run", "--project-root", str(PROJECT), "--verbose"]
    if compile_first:
        arguments.extend(["--features", "health_signal_normalized"])
    else:
        output = tmp_path / "plan.json"
        invoke(
            monkeypatch,
            "plan",
            "build",
            "--project-root",
            str(PROJECT),
            "--features",
            "health_signal_normalized",
            "--output",
            str(output),
        )
        capsys.readouterr()

        # Loading a saved plan must neither compile nor require analytics.
        def fail_compile(*args: object, **kwargs: object) -> None:
            pytest.fail("Saved-plan execution must not compile")

        monkeypatch.setattr(plan, "compile_plan", fail_compile)
        arguments.extend(["--compile", "false", "--plan", str(output)])
    invoke(monkeypatch, *arguments)
    text = capsys.readouterr().out
    assert "Engine completed the flow" in text
    assert "3 operations" in text
    assert "Calculated features: health_signal_normalized" in text
    assert "Execution stages" in text
    assert "Dataset(pump, pump_dataset): 5 features" in text


@pytest.mark.parametrize(
    "arguments",
    [
        ["analytics"],
        ["spec"],
        ["plan"],
        ["engine"],
        ["analytics", "unknown"],
        ["plan", "unknown"],
        ["engine", "unknown"],
        ["engine", "run", "--compile", "no"],
        ["engine", "run", "--compile", "false", "--features", "health_signal_normalized"],
        ["engine", "run", "--compile", "false", "--analytics", "analytics.json"],
        ["engine", "run", "--plan", "plan.json"],
    ],
)
def test_workflow_argument_errors(monkeypatch: pytest.MonkeyPatch, arguments: list[str]) -> None:
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, *arguments)
    assert error.value.code == 2


@pytest.mark.parametrize(
    "command",
    [["plan", "build"], ["analytics", "feature-graph"], ["engine", "run"]],
)
def test_workflow_missing_inputs_are_reported(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: list[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, *command, "--project-root", str(tmp_path))
    assert error.value.code == 1
    result = capsys.readouterr()
    assert "uptimely: error:" in result.err
    assert not result.out


@pytest.mark.parametrize("command", [["plan", "build"], ["analytics", "feature-graph"]])
def test_unknown_feature_is_reported(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], command: list[str]
) -> None:
    with pytest.raises(SystemExit) as error:
        invoke(
            monkeypatch,
            *command,
            "--analytics",
            str(ANALYTICS_PATH),
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
    config = tmp_path / "engine.json"
    config.write_text(content, encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        invoke(
            monkeypatch,
            "engine",
            "run",
            "--analytics",
            str(ANALYTICS_PATH),
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
    with pytest.raises(SystemExit) as error:
        invoke(
            monkeypatch,
            "engine",
            "run",
            "--analytics",
            str(ANALYTICS_PATH),
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


@pytest.mark.parametrize("content", [None, "not JSON", '{"plan_version": "unsupported"}'])
def test_engine_saved_plan_errors_are_reported(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    content: str | None,
) -> None:
    config = tmp_path / "config" / "engine.json"
    config.parent.mkdir()
    config.write_text("{}", encoding="utf-8")
    plan_path = tmp_path / "_generated/compile/execution_plan.json"
    if content is not None:
        plan_path.parent.mkdir(parents=True)
        plan_path.write_text(content, encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        invoke(
            monkeypatch,
            "engine",
            "run",
            "--project-root",
            str(tmp_path),
            "--compile",
            "false",
        )
    assert error.value.code == 1
    result = capsys.readouterr()
    assert "uptimely: error:" in result.err
    assert not result.out


@pytest.mark.parametrize("command", [["plan", "build"], ["analytics", "feature-graph"]])
def test_invalid_analytics_is_reported(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: list[str],
) -> None:
    analytics_definition = tmp_path / "analytics.json"
    analytics_definition.write_text("not JSON", encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, *command, "--analytics", str(analytics_definition))
    assert error.value.code == 1
    result = capsys.readouterr()
    assert "uptimely: error:" in result.err
    assert not result.out


def test_plan_write_errors_are_reported(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "plan.json"
    output.mkdir()
    with pytest.raises(SystemExit) as error:
        invoke(
            monkeypatch,
            "plan",
            "build",
            "--analytics",
            str(ANALYTICS_PATH),
            "--output",
            str(output),
        )
    assert error.value.code == 1
    assert "uptimely: error:" in capsys.readouterr().err


def test_workflows_import_project_functions_in_fresh_process(tmp_path: pathlib.Path) -> None:
    project = tmp_path / "project"
    (project / "_generated/analytics").mkdir(parents=True)
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
    (project / "_generated/analytics/analytics.json").write_text(
        json.dumps(
            {
                "version": "0.1.0",
                "functions": {
                    "read": {
                        "read_values": {
                            "entrypoint": "cli_project_functions:read_values",
                            "args": {"path": {"type": "string"}},
                        }
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
    for command in (
        ["plan", "build"],
        ["analytics", "feature-graph", "--verbose"],
        ["engine", "run", "--verbose"],
        ["engine", "run", "--compile", "false", "--verbose"],
    ):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "uptimely.cli.cli",
                *command,
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
        assert result.stdout
    assert (project / "_generated/compile/execution_plan.json").is_file()
