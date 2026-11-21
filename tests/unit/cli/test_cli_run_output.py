import json
import logging
import pathlib
import shlex
import sys
import types

import polars as pl
import pytest

from uptimely import application as application_module
from uptimely import engine as engine_module
from uptimely import plan as execution_plan
from uptimely.cli import cli
from uptimely.codebase import packaging
from uptimely.run import recording


def invoke(monkeypatch: pytest.MonkeyPatch, *arguments: str) -> None:
    monkeypatch.setattr(sys, "argv", ["uptimely", *arguments])
    cli.main()


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
            code=packaging.CodeArtifacts(language="python"),
        ),
    )
    (build_root / "build.json").write_text(json.dumps(manifest.model_dump()), encoding="utf-8")
    return build_root


@pytest.mark.parametrize("command", [("run",)])
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
    config = tmp_path / "config.toml"
    config.write_text("", encoding="utf-8")
    uptimely_logger = logging.getLogger("uptimely")
    previous_level = uptimely_logger.level
    dependency_logger = logging.getLogger("test_run_dependency")
    dependency_level = dependency_logger.level
    runtime_logger = logging.getLogger("uptimely.engine.test")

    def run(
        self: engine_module.Engine,
        *,
        validate: bool = False,
        src_path: pathlib.Path | None = None,
    ) -> engine_module.ExecutionResult:
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
            plan_version=execution_plan.PLAN_VERSION,
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
    assert ("Traceback (most recent call last):" in output.err) is (failed and level == "debug")
    assert ("View results in Explorer:" in output.out) is (
        not failed and level in ("debug", "info")
    )


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
    config = tmp_path / "config.toml"
    config.write_text("", encoding="utf-8")
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
        plan_version=execution_plan.PLAN_VERSION,
    )
    monkeypatch.setattr(
        engine_module.Engine,
        "run",
        lambda self, *, validate=False, preview_rows=5, src_path=None: result,
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
    assert "Engine processed 2 profiles in " in output.out
    assert output.out.rfind("View results in Explorer:") > output.out.index("Engine processed")
    assert "shape:" not in output.out
    if row_limit is None:
        assert "Profile:" not in output.out
        assert not collected_heights
    else:
        assert output.out.rfind("View results in Explorer:") > output.out.rfind("Profile: second")
        assert output.out.index("Engine processed") < output.out.index("Profile: first")
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
        invoke(monkeypatch, "run", "--preview", rows)
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
    config = tmp_path / "config.toml"
    config.write_text("", encoding="utf-8")
    result = engine_module.ExecutionResult(
        datasets={"values": frame},
        calculated_outputs={},
        invocation_statuses={},
        durations={},
        failures={},
        plan_version=execution_plan.PLAN_VERSION,
    )
    monkeypatch.setattr(
        engine_module.Engine,
        "run",
        lambda self, *, validate=False, preview_rows=5, src_path=None: result,
    )
    with pytest.raises(SystemExit) as error:
        invoke(
            monkeypatch,
            "run",
            "--project-root",
            str(tmp_path),
            "--config",
            str(config),
            "--preview",
        )
    assert error.value.code == 1
    output = capsys.readouterr()
    assert "ERROR    |" in output.err
    assert "Engine processed" in output.out
    assert "Profile:" not in output.out


@pytest.mark.parametrize("debug", [False, True])
@pytest.mark.parametrize("directory", ["project", "project with spaces"])
def test_engine_empty_plan_summary(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    debug: bool,
    directory: str,
) -> None:
    tmp_path = tmp_path / directory
    _write_empty_build(tmp_path)
    config = tmp_path / "config.toml"
    config.write_text("", encoding="utf-8")
    times = iter([10.0, 10.0])
    monkeypatch.setattr(cli.engine, "time", types.SimpleNamespace(perf_counter=lambda: next(times)))
    run_times = iter([10.0, 10.0])
    monkeypatch.setattr(
        recording, "time", types.SimpleNamespace(perf_counter=lambda: next(run_times))
    )
    arguments = ["--log-level", "debug"] if debug else []

    invoke(
        monkeypatch,
        "run",
        "--project-root",
        str(tmp_path),
        "--config",
        str(config),
        *arguments,
    )

    result = capsys.readouterr()
    assert not result.err
    command = result.out.split("View results in Explorer:\nINFO     | ", maxsplit=1)[1].strip()
    assert shlex.split(command) == [
        "uptimely",
        "explore",
        "--project-root",
        str(tmp_path.resolve()),
    ]
    summary = "INFO     | Engine processed 0 profiles in 0.000 s.\n"
    if debug:
        assert summary in result.out
        assert "Processed profiles:" not in result.out
    else:
        assert result.out == (
            "INFO     | Start Uptimely engine run\n"
            "INFO     | Start spec validation\n"
            "INFO     | Spec validated\n"
            + summary
            + "INFO     | View results in Explorer:\nINFO     | "
            + shlex.join(["uptimely", "explore", "--project-root", str(tmp_path.resolve())])
            + "\n"
        )
