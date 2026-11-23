import json
import pathlib
import shlex
import sys
import types

import pytest
from support import examples as example_support

from uptimely import application as application_module
from uptimely import engine as engine_module
from uptimely import plan as execution_plan
from uptimely.cli import cli
from uptimely.codebase import packaging
from uptimely.run import recording

PROJECT = example_support.EXAMPLES_ROOT


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
                "datasets": {},
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
        "feature-graph",
        "--project-root",
        str(PROJECT),
        "--features",
        "health_signal_normalized",
        "--log-level",
        "debug",
    )
    text = capsys.readouterr().out
    assert "Feature graph: 24 features" in text
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
    assert "Engine processed 4 profiles in " in text
    assert "Scope:" not in text
    assert "Processed profile pump: 8 features" in text
    assert "Processed profile pump_telemetry: 13 features" in text


@pytest.mark.parametrize("command", [("run",)])
@pytest.mark.parametrize("validate", [False, True])
def test_engine_cli_forwards_validation_flag(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    command: tuple[str, ...],
    validate: bool,
) -> None:
    _write_empty_build(tmp_path)
    config = tmp_path / "config.toml"
    config.write_text("", encoding="utf-8")
    received: list[bool] = []

    def run(
        self: engine_module.Engine,
        *,
        validate: bool = False,
        src_path: pathlib.Path | None = None,
    ) -> engine_module.ExecutionResult:
        received.append(validate)
        return engine_module.ExecutionResult(
            datasets={},
            calculated_outputs={},
            invocation_statuses={},
            durations={},
            failures={},
            plan_version=execution_plan.PLAN_VERSION,
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


def test_engine_cli_loads_named_config_profile_and_merges_defaults(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_empty_build(tmp_path)
    (tmp_path / "uptimely.toml").write_text(
        '[engine.backend]\nevaluation = "eager"\n[params]\nbase_value = 1\n',
        encoding="utf-8",
    )
    profile_dir = tmp_path / application_module.CONFIG_DIR
    profile_dir.mkdir()
    (profile_dir / "prod.toml").write_text(
        '[engine.backend]\ndataframe = "polars"\n[params]\nprofile_value = 2\n',
        encoding="utf-8",
    )

    def run(
        self: engine_module.Engine,
        *,
        validate: bool = False,
        src_path: pathlib.Path | None = None,
    ) -> engine_module.ExecutionResult:
        assert self.config.backend.evaluation == "eager"
        assert self.config.backend.dataframe == "polars"
        assert self.parameters == {"base_value": 1, "profile_value": 2}
        return engine_module.ExecutionResult(
            datasets={},
            calculated_outputs={},
            invocation_statuses={},
            durations={},
            failures={},
            plan_version=execution_plan.PLAN_VERSION,
        )

    monkeypatch.setattr(engine_module.Engine, "run", run)

    invoke(monkeypatch, "run", str(tmp_path), "--config", "prod")


@pytest.mark.parametrize(
    ("preview_args", "expected_preview_rows"),
    [([], 13), (["--preview"], 13), (["--preview", "7"], 7)],
)
def test_engine_cli_uses_project_preview_and_source_defaults(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    preview_args: list[str],
    expected_preview_rows: int,
) -> None:
    _write_empty_build(tmp_path)
    (tmp_path / "custom-src").mkdir()
    (tmp_path / "uptimely.toml").write_text(
        '[code]\nsrc = "custom-src"\n[engine]\npreview_rows = 13\n',
        encoding="utf-8",
    )
    received: list[tuple[int, pathlib.Path | None]] = []

    def run(
        self: engine_module.Engine,
        *,
        validate: bool = False,
        preview_rows: int | None = None,
        src_path: pathlib.Path | None = None,
    ) -> engine_module.ExecutionResult:
        configured_preview = self.config.preview_rows if preview_rows is None else preview_rows
        configured_src = (
            pathlib.Path(self.code_settings.src) if self.code_settings.src is not None else None
        )
        received.append((configured_preview, src_path or configured_src))
        return engine_module.ExecutionResult(
            datasets={},
            calculated_outputs={},
            invocation_statuses={},
            durations={},
            failures={},
            plan_version=execution_plan.PLAN_VERSION,
        )

    monkeypatch.setattr(engine_module.Engine, "run", run)

    invoke(monkeypatch, "run", str(tmp_path), *preview_args)

    assert received == [(expected_preview_rows, pathlib.Path("custom-src"))]


@pytest.mark.parametrize("command", [("run",)])
def test_engine_cli_builds_before_running(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: tuple[str, ...],
) -> None:
    _write_empty_build(tmp_path)
    config = tmp_path / "config.toml"
    config.write_text("", encoding="utf-8")
    events: list[str] = []
    src_path = pathlib.Path("local_python")

    def build(
        self: application_module.Uptimely, *, src_path: pathlib.Path | None = None
    ) -> application_module.BuildBundle:
        output = capsys.readouterr().out
        assert "Start Uptimely engine run" in output
        assert "Start building the project bundle" in output
        assert output.index("Start Uptimely engine run") < output.index(
            "Start building the project bundle"
        )
        events.append("build")
        assert self.root == tmp_path
        assert src_path == pathlib.Path("local_python")
        return self.load_build_bundle()

    def run(
        self: engine_module.Engine,
        *,
        validate: bool = False,
        src_path: pathlib.Path | None = None,
    ) -> engine_module.ExecutionResult:
        events.append("run")
        assert src_path == pathlib.Path("local_python")
        return engine_module.ExecutionResult(
            datasets={},
            calculated_outputs={},
            invocation_statuses={},
            durations={},
            failures={},
            plan_version=execution_plan.PLAN_VERSION,
        )

    monkeypatch.setattr(application_module.Uptimely, "build", build)
    monkeypatch.setattr(engine_module.Engine, "run", run)

    invoke(
        monkeypatch,
        *command,
        str(tmp_path),
        "--config",
        str(config),
        "--build",
        "--src-path",
        str(src_path),
    )

    assert events == ["build", "run"]


@pytest.mark.parametrize("command", [("run",)])
def test_engine_cli_does_not_run_after_build_failure(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: tuple[str, ...],
) -> None:
    def fail_build(
        self: application_module.Uptimely, *, src_path: pathlib.Path | None = None
    ) -> application_module.BuildBundle:
        raise application_module.ProjectBuildError("generation", "invalid source")

    monkeypatch.setattr(application_module.Uptimely, "build", fail_build)
    monkeypatch.setattr(
        engine_module.Engine,
        "run",
        lambda *_args, **_kwargs: pytest.fail("Engine must not run after a failed build"),
    )

    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, *command, str(tmp_path), "--build")

    assert error.value.code == 1
    assert "Project build generation failed: invalid source" in capsys.readouterr().err


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

    invoke(monkeypatch, "run", "--project-root", str(project_root))

    result = capsys.readouterr()
    assert not result.err
    dataset_count = 4 if scoped else 10
    lines = result.out.splitlines()
    assert lines[0] == "INFO     | Start Uptimely engine run"
    assert "Start building the project bundle" not in result.out
    assert lines[1] == "INFO     | Start spec validation"
    assert lines[2] == "INFO     | Spec validated"
    processed_profiles = [line for line in lines[1:] if "Processed profile " in line]
    assert len(processed_profiles) == dataset_count
    assert all(line.startswith("INFO     | ") for line in processed_profiles)
    assert any("Processed profile pump: 8 features" in line for line in processed_profiles)
    assert lines[-3] == (f"INFO     | Engine processed {dataset_count} profiles in 1.234 s.")
    assert all(lines.index(line) < len(lines) - 3 for line in processed_profiles)
    assert lines[-2] == "INFO     | View results in Explorer:"
    assert lines[-1] == (
        "INFO     | "
        + shlex.join(["uptimely", "explore", "--project-root", str(project_root.resolve())])
    )
    assert "Scope:" not in result.out
