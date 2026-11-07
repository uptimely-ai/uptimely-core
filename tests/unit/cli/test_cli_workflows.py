"""Tests for spec, plan, and engine command groups."""

import json
import logging
import pathlib
import sys
import types

import polars as pl
import pytest
from support import examples as example_support

from uptimely import engine as engine_module
from uptimely import project as project_module
from uptimely.cli import cli
from uptimely.run import recording

PROJECT = example_support.EXAMPLES_ROOT / "pump_analytics"
SPEC_PATH = PROJECT / "_generated/build/spec.json"


def invoke(monkeypatch: pytest.MonkeyPatch, *arguments: str) -> None:
    monkeypatch.setattr(sys, "argv", ["uptimely", *arguments])
    cli.main()


def _copy_pump_project(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    features: tuple[str, ...] | None = None,
) -> pathlib.Path:
    project_root = tmp_path / "examples" / "pump_analytics"
    example_support.copy_example_project(project_root, features=features)
    (project_root.parent / "__init__.py").write_text("", encoding="utf-8")
    return project_root


@pytest.mark.usefixtures("example_projects")
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
        "--log-level",
        "debug",
    )
    text = capsys.readouterr().out
    assert "Feature graph: 13 features" in text
    assert "Selected feature subset: 2 features" in text
    assert "health_signal_normalized" in text
    assert "Selected feature subset\n" in text


def test_engine_run_consumes_scoped_build_without_compiling(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project_root = _copy_pump_project(tmp_path, monkeypatch, features=("health_signal_normalized",))

    def fail_compile(*args: object, **kwargs: object) -> None:
        pytest.fail("Engine execution must not compile")

    monkeypatch.setattr("uptimely.compiler.Compiler.compile", fail_compile)
    invoke(monkeypatch, "run", str(project_root), "--log-level", "debug")
    text = capsys.readouterr().out
    assert "Engine completed in " in text
    assert "2 profiles processed" in text
    assert "Scope: selected features: health_signal_normalized" in text
    assert "- Profile: pump_profile - 6 features" in text


@pytest.mark.parametrize("command", [("run",), ("engine", "run")])
@pytest.mark.parametrize("validate", [False, True])
def test_engine_cli_forwards_validation_flag(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    command: tuple[str, ...],
    validate: bool,
) -> None:
    _write_empty_build(tmp_path)
    config = tmp_path / "config.json"
    config.write_text("{}", encoding="utf-8")
    received: list[bool] = []

    def run(self: engine_module.Engine, *, validate: bool = False) -> engine_module.ExecutionResult:
        received.append(validate)
        return engine_module.ExecutionResult(
            datasets={},
            calculated_outputs={},
            invocation_statuses={},
            durations={},
            failures={},
            plan_version=6,
        )

    monkeypatch.setattr(engine_module.Engine, "run", run)
    invoke(
        monkeypatch,
        *command,
        str(tmp_path),
        "--config",
        str(config),
        *(["--validate"] if validate else []),
    )

    assert received == [validate]


@pytest.mark.parametrize("scoped", [False, True])
def test_engine_default_logs_only_duration_and_processed_profiles(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    scoped: bool,
) -> None:
    project_root = _copy_pump_project(
        tmp_path, monkeypatch, features=("health_signal_normalized",) if scoped else None
    )
    times = iter([10.0, 11.234])
    monkeypatch.setattr(cli.engine, "time", types.SimpleNamespace(perf_counter=lambda: next(times)))
    run_times = iter([10.0, 11.234])
    monkeypatch.setattr(
        recording, "time", types.SimpleNamespace(perf_counter=lambda: next(run_times))
    )
    capsys.readouterr()

    invoke(monkeypatch, "engine", "run", "--project-root", str(project_root))

    result = capsys.readouterr()
    assert not result.err
    dataset_count = 2 if scoped else 3
    assert result.out.splitlines() == [
        "",
        f"Engine completed in 1.234 s: {dataset_count} profiles processed",
    ]


@pytest.mark.parametrize("command", [("run",), ("engine", "run")])
@pytest.mark.parametrize("level", ["debug", "info", "warning", "error", "critical"])
@pytest.mark.parametrize("failed", [False, True])
def test_run_log_level_filters_uptimely_only_and_restores_configuration(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: tuple[str, ...],
    level: str,
    failed: bool,
) -> None:
    _write_empty_build(tmp_path)
    config = tmp_path / "config.json"
    config.write_text("{}", encoding="utf-8")
    uptimely_logger = logging.getLogger("uptimely")
    previous_level = uptimely_logger.level
    dependency_logger = logging.getLogger("test_run_dependency")
    dependency_level = dependency_logger.level
    runtime_logger = logging.getLogger("uptimely.engine.test")

    def run(self: engine_module.Engine, *, validate: bool = False) -> engine_module.ExecutionResult:
        assert validate
        assert logging.getLogger().level == logging.INFO
        assert dependency_logger.level == dependency_level
        assert not dependency_logger.isEnabledFor(logging.DEBUG)
        runtime_logger.debug("validation debug trace")
        runtime_logger.info("runtime info")
        runtime_logger.warning("runtime warning")
        runtime_logger.error("runtime error")
        runtime_logger.critical("runtime critical")
        if failed:
            raise RuntimeError("execution failed")
        return engine_module.ExecutionResult(
            datasets={},
            calculated_outputs={},
            invocation_statuses={},
            durations={},
            failures={},
            plan_version=6,
        )

    monkeypatch.setattr(engine_module.Engine, "run", run)
    arguments = (
        *command,
        str(tmp_path),
        "--config",
        str(config),
        "--validate",
        "--log-level",
        level,
    )
    if failed:
        with pytest.raises(SystemExit) as error:
            invoke(monkeypatch, *arguments)
        assert error.value.code == 1
    else:
        invoke(monkeypatch, *arguments)
    assert uptimely_logger.level == previous_level
    output = capsys.readouterr()
    assert ("validation debug trace" in output.out) is (level == "debug")
    for message_level in ("info", "warning", "error", "critical"):
        assert (f"runtime {message_level}" in output.out) is (
            getattr(logging, message_level.upper()) >= getattr(logging, level.upper())
        )
    assert ("execution failed" in output.err) is failed


@pytest.mark.parametrize("lazy", [False, True])
@pytest.mark.parametrize("row_count", [0, 3, 15])
@pytest.mark.parametrize(
    ("arguments", "row_limit"),
    [
        ([], None),
        (["--preview"], 5),
        (["--preview", "1"], 1),
        (["--preview", "12", "--log-level", "debug"], 12),
    ],
)
def test_engine_previews_final_profiles(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    lazy: bool,
    row_count: int,
    arguments: list[str],
    row_limit: int | None,
) -> None:
    _write_empty_build(tmp_path)
    config = tmp_path / "config.json"
    config.write_text("{}", encoding="utf-8")
    frame = pl.DataFrame(
        {"value": [f"row_{index:02d}" for index in range(row_count)]},
        schema={"value": pl.String},
    ).with_columns(pl.lit(index).alias(f"c{index}") for index in range(10))
    output_frame = frame.lazy() if lazy else frame
    result = engine_module.ExecutionResult(
        datasets={"first": output_frame, "second": output_frame},
        calculated_outputs={},
        invocation_statuses={},
        durations={},
        failures={},
        plan_version=6,
    )
    monkeypatch.setattr(
        engine_module.Engine, "run", lambda self, *, validate=False, preview_rows=5: result
    )
    collected_heights: list[int] = []
    original_collect = pl.LazyFrame.collect

    def collect(frame: pl.LazyFrame) -> pl.DataFrame:
        collected = original_collect(frame)
        collected_heights.append(collected.height)
        return collected

    monkeypatch.setattr(pl.LazyFrame, "collect", collect)
    with pl.Config(tbl_rows=2, tbl_cols=2, tbl_hide_dataframe_shape=False):
        original_config = pl.Config.state()
        invoke(
            monkeypatch,
            "engine",
            "run",
            "--project-root",
            str(tmp_path),
            "--config",
            str(config),
            *arguments,
        )
        assert pl.Config.state() == original_config

    output = capsys.readouterr()
    assert not output.err
    assert "2 profiles processed" in output.out
    assert "shape:" not in output.out
    if row_limit is None:
        assert "Profile:" not in output.out
        assert not collected_heights
    else:
        assert output.out.index("Engine completed") < output.out.index("Profile: first")
        if "debug" in arguments:
            assert output.out.index("Processed profiles:") < output.out.index("Profile: first")
        for dataset in ("first", "second"):
            assert f"Profile: {dataset}\n" in output.out
            assert f"Dataset(sample, {dataset}):\n" not in output.out
        assert " rows:" not in output.out
        for column in frame.columns:
            assert column in output.out
        expected_rows = min(row_limit, row_count)
        for index in range(expected_rows):
            assert output.out.count(f"row_{index:02d}") == 2
        assert f"row_{expected_rows:02d}" not in output.out
        assert collected_heights == ([expected_rows, expected_rows] if lazy else [])
    assert frame.height == row_count


@pytest.mark.parametrize("rows", ["0", "-1", "bad", "1.5"])
def test_engine_rejects_invalid_preview_before_execution(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], rows: str
) -> None:
    def fail_run(self: engine_module.Engine) -> engine_module.ExecutionResult:
        pytest.fail("Invalid preview arguments must fail before execution")

    monkeypatch.setattr(engine_module.Engine, "run", fail_run)
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, "engine", "run", "--preview", rows)
    assert error.value.code == 2
    output = capsys.readouterr()
    assert "--preview" in output.err
    assert not output.out


@pytest.mark.parametrize("frame", [object(), pl.LazyFrame().select(pl.col("missing"))])
def test_engine_preview_errors_are_reported(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    frame: object,
) -> None:
    _write_empty_build(tmp_path)
    config = tmp_path / "config.json"
    config.write_text("{}", encoding="utf-8")
    result = engine_module.ExecutionResult(
        datasets={"values": frame},
        calculated_outputs={},
        invocation_statuses={},
        durations={},
        failures={},
        plan_version=6,
    )
    monkeypatch.setattr(
        engine_module.Engine, "run", lambda self, *, validate=False, preview_rows=5: result
    )
    with pytest.raises(SystemExit) as error:
        invoke(
            monkeypatch,
            "engine",
            "run",
            "--project-root",
            str(tmp_path),
            "--config",
            str(config),
            "--preview",
        )
    assert error.value.code == 1
    output = capsys.readouterr()
    assert "uptimely: error:" in output.err
    assert "Engine completed" in output.out
    assert "Profile:" not in output.out


@pytest.mark.parametrize("debug", [False, True])
def test_engine_empty_plan_summary(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    debug: bool,
) -> None:
    _write_empty_build(tmp_path)
    config = tmp_path / "config.json"
    config.write_text("{}", encoding="utf-8")
    times = iter([10.0, 10.0])
    monkeypatch.setattr(cli.engine, "time", types.SimpleNamespace(perf_counter=lambda: next(times)))
    run_times = iter([10.0, 10.0])
    monkeypatch.setattr(
        recording, "time", types.SimpleNamespace(perf_counter=lambda: next(run_times))
    )
    arguments = ["--log-level", "debug"] if debug else []

    invoke(
        monkeypatch,
        "engine",
        "run",
        "--project-root",
        str(tmp_path),
        "--config",
        str(config),
        *arguments,
    )

    result = capsys.readouterr()
    assert not result.err
    summary = "\nEngine completed in 0.000 s: 0 profiles processed\n"
    if debug:
        assert summary in result.out
        assert "\nScope: all features\n" in result.out
        assert "\nProcessed profiles:\n" in result.out
    else:
        assert result.out == summary


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
        ["engine", "run", "--verbose"],
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
            "uptimely.engine.Engine.run",
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


@pytest.mark.parametrize("content", ["not JSON", "[]", '{"bind": []}', '{"unknown": true}'])
def test_engine_invalid_config_is_reported(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    content: str,
) -> None:
    _write_empty_build(tmp_path)
    config = tmp_path / "config.json"
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
    config = tmp_path / "config.json"
    config.write_text('{"params": {}}', encoding="utf-8")
    project_root = _copy_pump_project(tmp_path, monkeypatch, features=("health_signal_normalized",))
    with pytest.raises(SystemExit) as error:
        invoke(
            monkeypatch,
            "engine",
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
    assert "Unresolved parameter:" in result.err
    assert "Engine completed" not in result.out
    assert "Profile:" not in result.out


def test_engine_config_loads_backend_and_params() -> None:
    settings = engine_module.Config.model_validate_json(
        '{"engine": {"backend": {"dataframe": "polars"}}, "params": {"threshold": 10}}'
    )
    assert settings.engine.backend.dataframe == "polars"
    assert settings.params.root == {"threshold": 10}


def _write_empty_build(project_root: pathlib.Path) -> pathlib.Path:
    build_root = project_root / project_module.BUILD_OUTPUT_DIR
    explorer_root = build_root / "explorer"
    explorer_root.mkdir(parents=True)
    (build_root / "spec.json").write_text("{}", encoding="utf-8")
    (build_root / "execution_plan.json").write_text(
        json.dumps(
            {
                "plan_version": 6,
                "required_backend": "polars",
                "resources": {},
                "invocations": [],
                "stages": [],
            }
        ),
        encoding="utf-8",
    )
    (explorer_root / "index.html").write_text("<html></html>", encoding="utf-8")
    manifest = project_module.BuildManifest(
        build_version=project_module.BUILD_VERSION,
        uptimely_version="0.2.0",
        features=None,
        artifacts=project_module.BuildArtifactPaths(
            spec="spec.json",
            execution_plan="execution_plan.json",
        ),
    )
    (build_root / "build.json").write_text(json.dumps(manifest.model_dump()), encoding="utf-8")
    return build_root


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
