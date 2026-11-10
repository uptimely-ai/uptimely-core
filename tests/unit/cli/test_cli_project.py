"""Tests for building and publishing project bundles without executing workflows."""

import json
import logging
import os
import pathlib
import shutil
import subprocess
import sys
import threading
from collections import abc

import pytest
from support import examples as example_support

from uptimely import plan as plan_module
from uptimely import project, spec
from uptimely.cli import cli
from uptimely.compiler import compiler as compiler_module
from uptimely.project.build import builder as project_build

REPOSITORY_ROOT = pathlib.Path(__file__).parents[3]


def invoke(monkeypatch: pytest.MonkeyPatch, *arguments: str) -> None:
    monkeypatch.setattr(sys, "argv", ["uptimely", "project", "build", *arguments])
    cli.main()


def copy_project_spec(root: pathlib.Path) -> pathlib.Path:
    bundle = example_support.example_bundle()
    source = root / project.SPEC_JSON_ENTRY_FILE
    source.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(bundle.spec_path, source)
    return source


def bundle_files(root: pathlib.Path) -> dict[str, bytes]:
    build_root = root / project.BUILD_OUTPUT_DIR
    return {
        path.relative_to(build_root).as_posix(): path.read_bytes()
        for path in build_root.rglob("*")
        if path.is_file()
    }


def copy_unbuilt_example(tmp_path: pathlib.Path) -> pathlib.Path:
    examples = tmp_path / "examples"
    examples.mkdir()
    shutil.copyfile(REPOSITORY_ROOT / "examples/__init__.py", examples / "__init__.py")
    root = examples / "pump_analytics"
    shutil.copytree(
        REPOSITORY_ROOT / "examples" / "pump_analytics",
        root,
        ignore=shutil.ignore_patterns("_generated", "__pycache__"),
    )
    return root


@pytest.mark.parametrize(
    "debug",
    [False, True],
)
@pytest.mark.parametrize("explicit_root", [False, True])
@pytest.mark.parametrize("empty_generated", [False, True])
def test_project_build_examples(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    debug: bool,
    explicit_root: bool,
    empty_generated: bool,
) -> None:
    root = copy_unbuilt_example(tmp_path)
    if empty_generated:
        (root / project.GENERATED_DIR).mkdir()
    arguments = ["--project-root", str(root)] if explicit_root else []
    if debug:
        arguments.extend(["--log-level", "debug"])
    monkeypatch.chdir(tmp_path if explicit_root else root)
    invoke(monkeypatch, *arguments)
    result = capsys.readouterr()

    assert not result.err
    if debug:
        assert "Check operator feature dependencies are acyclic" in result.out
        assert result.out.count("Check feature selection is a collection, not a string") == 1
        assert (
            result.out.index("Check spec version is an integer")
            < result.out.index("Check globally unique profile IDs")
            < result.out.index("Check feature selection is a collection, not a string")
        )
        assert "Check dependency graph is acyclic and schedulable" in result.out
        assert "\nCompiler operator: " not in result.out
        assert result.out.count("Check functions declare entrypoints") == 1
        assert result.out.count("Check structural argument references resolve") == 1
        assert result.out.count("Creating portable invocation representations") == 1
        assert result.out.count("Check syntax for ") == 1
        assert result.out.count("Check package ownership for ") == 1
        assert result.out.count("Check callable signatures for ") == 1
        assert "\nCompiler function:" not in result.out
        assert result.out.index("Build summary\n+") > result.out.index(
            "Check emitted invocation IDs, dependencies, and stage ordering"
        )
        assert "Compiled plan:" not in result.out
        assert result.out.count("Check spec version is an integer") == 1
        for line in result.out.splitlines():
            if " | " in line and not line.startswith("|"):
                level, message = line.split(" | ", maxsplit=1)
                assert len(level) == 8
                assert message == message.lstrip()
                assert not message.startswith("- ")
                assert not message.endswith(":")
        assert result.out.endswith(f"Build files created to {root / project.BUILD_OUTPUT_DIR}\n")
        assert "| Build   | Build scope" in result.out
        assert "| all features" in result.out
        source = REPOSITORY_ROOT / "examples" / "pump_analytics" / project.SPEC_PYTHON_ENTRY_FILE
        assert f"| {source}" in result.out
    else:
        assert result.out == (
            "INFO     | Start spec validation\n"
            "INFO     | Spec validated\n"
            f"{'INFO':8} | "
            f"Build files created to {root / project.BUILD_OUTPUT_DIR}\n"
        )
    bundle = project.load_build_bundle(root)
    assert bundle.manifest.features is None
    assert spec.load_spec(bundle.spec_path).profiles
    assert bundle.execution_plan.invocations
    assert set(bundle_files(root)) == {"build.json", "execution_plan.json", "spec.json"}
    explorer_data = json.loads((root / project.EXPLORER_DATA_FILE).read_text(encoding="utf-8"))
    assert explorer_data["format_version"] == 3


def test_installed_console_script_builds_example(tmp_path: pathlib.Path) -> None:
    root = copy_unbuilt_example(tmp_path)
    executable = shutil.which("uptimely")
    assert executable is not None, "The installed uptimely console script is required"
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)

    result = subprocess.run(
        [executable, "project", "build"],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=90,
    )

    assert result.returncode == 0, result.stderr
    assert not result.stderr
    assert result.stdout == (
        "INFO     | Start spec validation\n"
        "INFO     | Spec validated\n"
        f"{'INFO':8} | "
        f"Build files created to {root / project.BUILD_OUTPUT_DIR}\n"
    )
    bundle = project.load_build_bundle(root)
    assert bundle.manifest.features is None
    assert spec.load_spec(bundle.spec_path).profiles
    assert bundle.execution_plan.invocations
    assert (root / project.EXPLORER_DATA_FILE).is_file()


def test_project_rebuild_replaces_previous_bundle(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = example_support.copy_example_project(tmp_path / "examples" / "pump_analytics")
    (root.parent / "__init__.py").write_text("", encoding="utf-8")
    bundle = project.load_build_bundle(root)
    old_plan = bundle.execution_plan
    old_spec = bundle.spec_path.read_bytes()
    stale_file = bundle.root / "stale.html"
    stale_file.write_text("stale", encoding="utf-8")

    invoke(monkeypatch, "--project-root", str(root))

    rebuilt_bundle = project.load_build_bundle(root)
    assert rebuilt_bundle.spec_path.read_bytes() == old_spec
    assert {item.id: item for item in rebuilt_bundle.execution_plan.invocations} == {
        item.id: item for item in old_plan.invocations
    }
    assert len(rebuilt_bundle.execution_plan.execution_stages) == len(old_plan.execution_stages)
    assert not (rebuilt_bundle.root / "stale.html").exists()
    assert not (root / "_generated/spec/spec.json").exists()
    assert not (root / "_generated/compile/execution_plan.json").exists()


@pytest.mark.parametrize("source_kind", ["entrypoint", "json"])
@pytest.mark.parametrize("debug", [False, True])
def test_project_build_explicit_source_does_not_execute_workflow(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    source_kind: str,
    debug: bool,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delitem(sys.modules, "declaration", raising=False)
    monkeypatch.delitem(sys.modules, "build_functions", raising=False)
    root = tmp_path / "project"
    root.mkdir()
    (root / "build_functions.py").write_text(
        "import polars\n"
        "def read() -> polars.DataFrame:\n"
        "    raise RuntimeError('Build must not execute spec')\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(root))
    source = tmp_path / "source.json"
    source.write_text(
        json.dumps(
            {
                "spec_version": 8,
                "name": "Build-only test",
                "functions": {
                    "read": {
                        "entrypoint": "build_functions:read",
                        "returns": "dataframe",
                    }
                },
                "profiles": {
                    "values": {
                        "features": {"value": {}},
                        "assembly": {
                            "read": {
                                "compute": {"function": "read"},
                                "interface": {"outputs": ["$features.value"]},
                            }
                        },
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    if source_kind != "json":
        (root / "declaration.py").write_text(
            "from uptimely.spec import python as api\n"
            "from uptimely.spec.python import Binding, Feature, Interface, Operator, Profile\n"
            "import build_functions\n"
            "class Values(Profile):\n"
            "    id = 'values'\n"
            "    assembly = [Operator(\n"
            "        id='read',\n"
            "        interface=Interface(outputs=[Feature(id='value')]),\n"
            "        compute=Binding(\n"
            "            function=api.ref.function(build_functions.read, returns='dataframe'),\n"
            "        ),\n"
            "    )]\n"
            "definition = api.Spec(profiles=[Values])\n",
            encoding="utf-8",
        )
        arguments = ["--python-spec", "declaration:definition"]
    else:
        arguments = ["--json-spec", "source.json"]

    if debug:
        arguments.extend(["--log-level", "debug"])
    invoke(monkeypatch, "--project-root", str(root), *arguments)

    result = capsys.readouterr()
    bundle = project.load_build_bundle(root)
    assert not result.err
    if debug:
        source_file = root / "declaration.py" if source_kind != "json" else source
        rows = [
            [cell.strip() for cell in line.split("|")[1:-1]]
            for line in result.out.splitlines()
            if line.startswith("|")
        ]
        assert ["Spec", "Spec source file", str(source_file)] in rows
        assert ["Spec", "Number of functions", "1"] in rows
        assert ["Spec", "Number of profiles", "1"] in rows
        assert ["Spec", "Number of features", "1"] in rows
    else:
        assert result.out == (
            "INFO     | Start spec validation\n"
            "INFO     | Spec validated\n"
            f"{'INFO':8} | "
            f"Build files created to {bundle.root}\n"
        )
    assert spec.load_spec(bundle.spec_path).profiles
    assert bundle.execution_plan.invocations
    assert (root / project.EXPLORER_DATA_FILE).is_file()
    assert not (root / "_generated/spec").exists()
    assert (root / project.EXPLORER_DATA_FILE).is_file()


@pytest.mark.parametrize("scoped", [False, True])
def test_project_build_debug_summary(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    scoped: bool,
) -> None:
    root = tmp_path / "project"
    source = copy_project_spec(root)
    definition = spec.load_spec(source)
    profiles = list(definition.profiles.values())
    times = iter([10.0, 11.234])
    monkeypatch.setattr(cli.project.time, "perf_counter", lambda: next(times))
    arguments = ["--features", "pump_health_score"] if scoped else []

    invoke(monkeypatch, "--project-root", str(root), "--log-level", "debug", *arguments)

    result = capsys.readouterr()
    bundle = project.load_build_bundle(root)
    scope = "pump_health_score" if scoped else "all features"
    assert not result.err
    rows = [
        [cell.strip() for cell in line.split("|")[1:-1]]
        for line in result.out.splitlines()
        if line.startswith("|")
    ]
    assert rows == [
        ["Section", "Detail", "Value"],
        ["Build", "Duration", "1.234 s"],
        ["Build", "Output folder", str(bundle.root)],
        ["Build", "Build scope", scope],
        ["Spec", "Spec source file", str(source)],
        ["Spec", "Number of functions", str(len(definition.functions))],
        ["Spec", "Number of profiles", str(len(profiles))],
        ["Spec", "Number of features", str(sum(len(profile.features) for profile in profiles))],
        ["Plan", "Number of stages", str(len(bundle.execution_plan.stages))],
        ["Plan", "Number of invocations", str(len(bundle.execution_plan.invocations))],
    ]
    assert result.out.index("Build summary\n+") > result.out.index(
        "Check emitted invocation IDs, dependencies, and stage ordering"
    )
    assert "Compiled plan:" not in result.out
    assert result.out.index("| Plan") > result.out.index("Check spec version is an integer")
    assert result.out.endswith(f"Build files created to {bundle.root}\n")


def test_failed_build_prints_trace_without_summary_and_preserves_logging(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = logging.getLogger("uptimely")
    handlers, propagate = target.handlers[:], target.propagate

    def fail_build(*args: object, **kwargs: object) -> None:
        logging.getLogger("uptimely.project.build").debug("attempting build")
        logging.getLogger("uptimely.project.build").warning("build warning")
        raise ValueError("injected failure")

    monkeypatch.setattr(cli.project.project_build, "build_project", fail_build)

    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, "--project-root", str(tmp_path), "--log-level", "debug")

    result = capsys.readouterr()
    assert error.value.code == 1
    assert result.out == (f"{'DEBUG':8} | attempting build\n{'WARNING':8} | build warning\n")
    assert "\nBuild summary" not in result.out
    assert "injected failure" in result.err
    assert "Traceback (most recent call last):" in result.err
    assert "fail_build" in result.err
    assert target.handlers == handlers
    assert target.propagate == propagate


def test_project_build_keeps_warnings_visible(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "project"
    copy_project_spec(root)
    original_compile = project_build.compiler.Compiler.compile

    def compile_with_warning(
        self: project_build.compiler.Compiler,
        spec_definition: spec.Spec,
        features: abc.Collection[str] | None = None,
    ) -> plan_module.ExecutionPlan:
        compiler_module.logger.warning("Build warning")
        return original_compile(self, spec_definition, features)

    monkeypatch.setattr(project_build.compiler.Compiler, "compile", compile_with_warning)

    invoke(monkeypatch, "--project-root", str(root))

    result = capsys.readouterr()
    assert not result.err
    assert result.out == (
        f"{'WARNING':8} | Build warning\n"
        "INFO     | Start spec validation\n"
        "INFO     | Spec validated\n"
        f"{'INFO':8} | "
        f"Build files created to {root / project.BUILD_OUTPUT_DIR}\n"
    )


def test_scoped_build_normalizes_features_and_includes_dataset_sink(
    tmp_path: pathlib.Path,
) -> None:
    root = tmp_path / "project"
    source = copy_project_spec(root)
    source_spec = spec.load_spec(source)

    bundle = project_build.build_project(
        root,
        features=["pump_health_score", "pump_health_score"],
    )

    assert bundle.manifest.features == ["pump_health_score"]
    plan_invocations = bundle.execution_plan.invocations
    sinks = [invocation for invocation in plan_invocations if invocation.operator_kind == "write"]
    assert sinks
    plan_ids = {invocation.id for invocation in plan_invocations}
    produced_features = {
        feature for invocation in plan_invocations for feature in invocation.output_features
    }
    dimensions = set(source_spec.identifier_ids)
    for invocation in plan_invocations:
        assert set(invocation.dependency_ids) <= plan_ids
    for sink in sinks:
        assert set(sink.input_features) <= produced_features | dimensions
    full_plan = example_support.example_bundle().execution_plan
    assert len(bundle.execution_plan.invocations) <= len(full_plan.invocations)
    assert len({invocation.id for invocation in bundle.execution_plan.invocations}) == len(
        bundle.execution_plan.invocations
    )
    full_bundle = project_build.build_project(root)
    assert full_bundle.manifest.features is None


def test_project_build_compiles_once_and_prepares_the_compiled_plan(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "project"
    copy_project_spec(root)
    plans: list[plan_module.ExecutionPlan] = []
    compiled: list[plan_module.ExecutionPlan] = []
    original_compile = project_build.compiler.Compiler.compile
    original_build_presentation = project_build.presentation.build_presentation_data

    def compile_once(
        self: project_build.compiler.Compiler,
        spec_definition: spec.Spec,
        features: abc.Collection[str] | None = None,
    ) -> plan_module.ExecutionPlan:
        compiled_plan = original_compile(self, spec_definition, features)
        compiled.append(compiled_plan)
        return compiled_plan

    def prepare_compiled_plan(
        spec_definition: spec.Spec,
        plan: plan_module.ExecutionPlan,
        **kwargs: object,
    ) -> project_build.presentation.ExplorerPresentationData:
        plans.append(plan)
        return original_build_presentation(spec_definition, plan, **kwargs)

    monkeypatch.setattr(project_build.compiler.Compiler, "compile", compile_once)
    monkeypatch.setattr(
        project_build.presentation, "build_presentation_data", prepare_compiled_plan
    )

    project_build.build_project(root)

    assert len(compiled) == 1
    assert len(plans) == 1
    assert plans[0] is compiled[0]


@pytest.mark.parametrize(
    ("stage", "expected"),
    [
        ("compile", "Project build compilation failed"),
        ("presentation", "Project build artifact generation failed"),
        ("publish", "Project build publication failed"),
    ],
)
@pytest.mark.parametrize("debug", [False, True])
def test_project_build_failures_preserve_previous_bundle(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stage: str,
    expected: str,
    debug: bool,
) -> None:
    root = tmp_path / "project"
    copy_project_spec(root)
    shutil.copytree(example_support.example_bundle().root, root / project.BUILD_OUTPUT_DIR)
    old_bundle = bundle_files(root)
    snapshot = root / project.EXPLORER_DATA_FILE
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text("previous snapshot", encoding="utf-8")

    if stage == "compile":

        def fail_compile(
            self: object,
            spec_definition: spec.Spec,
            features: abc.Collection[str] | None = None,
        ) -> None:
            raise ValueError("Injected compile failure")

        monkeypatch.setattr(project_build.compiler.Compiler, "compile", fail_compile)
    elif stage == "presentation":

        def fail_presentation(*args: object, **kwargs: object) -> None:
            raise OSError("Injected presentation failure")

        monkeypatch.setattr(
            project_build.presentation, "build_presentation_data", fail_presentation
        )
    else:
        original_replace = project_build.os.replace
        call_count = 0

        def fail_install(source: pathlib.Path, target: pathlib.Path) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise OSError("Injected publication failure")
            original_replace(source, target)

        monkeypatch.setattr(project_build.os, "replace", fail_install)

    with pytest.raises(SystemExit) as error:
        arguments = ["--log-level", "debug"] if debug else []
        invoke(monkeypatch, "--project-root", str(root), *arguments)

    assert error.value.code == 1
    result = capsys.readouterr()
    assert expected in result.err
    assert f"Build files created to {root / project.BUILD_OUTPUT_DIR}" not in result.out
    assert bundle_files(root) == old_bundle
    assert snapshot.read_text(encoding="utf-8") == "previous snapshot"
    assert not list((root / project.GENERATED_DIR).glob(".build-staging-*"))
    assert not list((root / project.GENERATED_DIR).glob(".build-backup-*"))


def test_snapshot_publication_failure_preserves_previous_snapshot(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "project"
    copy_project_spec(root)
    snapshot = root / project.EXPLORER_DATA_FILE
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text("previous snapshot", encoding="utf-8")
    original_replace = project_build.os.replace

    def fail_snapshot_replace(source: pathlib.Path, target: pathlib.Path) -> None:
        if target == snapshot:
            raise OSError("injected snapshot failure")
        original_replace(source, target)

    monkeypatch.setattr(project_build.os, "replace", fail_snapshot_replace)

    with pytest.raises(project.ProjectBuildError, match="Explorer snapshot publication failed"):
        project_build.build_project(root)

    assert project.load_build_bundle(root).manifest.build_version == project.BUILD_VERSION
    assert snapshot.read_text(encoding="utf-8") == "previous snapshot"
    assert not list(snapshot.parent.glob(f".{snapshot.name}.*.tmp"))


def test_snapshot_readers_observe_complete_old_or_new_data(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = tmp_path / project.EXPLORER_DATA_FILE
    snapshot.parent.mkdir(parents=True)
    previous = b'{"generation":"previous"}'
    replacement = '{"generation":"replacement"}'
    snapshot.write_bytes(previous)
    replacement_ready = threading.Event()
    allow_replace = threading.Event()
    failures: list[Exception] = []
    original_replace = project_build.os.replace

    def pause_before_replace(source: pathlib.Path, target: pathlib.Path) -> None:
        try:
            assert target == snapshot
            assert source.read_bytes() == replacement.encode()
            replacement_ready.set()
            if not allow_replace.wait(timeout=5):
                raise TimeoutError("Timed out waiting to replace the snapshot")
            original_replace(source, target)
        except Exception as error:
            failures.append(error)
            raise

    monkeypatch.setattr(project_build.os, "replace", pause_before_replace)
    writer = threading.Thread(
        target=project_build._publish_explorer_snapshot,
        args=(tmp_path, replacement),
    )
    writer.start()
    try:
        assert replacement_ready.wait(timeout=5)
        assert snapshot.read_bytes() == previous
    finally:
        allow_replace.set()
    writer.join(timeout=5)

    assert not writer.is_alive()
    assert failures == []
    assert snapshot.read_bytes() == replacement.encode()


@pytest.mark.parametrize("exclusive", [False, True])
def test_project_build_fails_while_bundle_lock_is_held(
    tmp_path: pathlib.Path,
    exclusive: bool,
) -> None:
    root = tmp_path / "project"
    copy_project_spec(root)
    shutil.copytree(example_support.example_bundle().root, root / project.BUILD_OUTPUT_DIR)

    with (
        project.build_lock(root, exclusive=exclusive),
        pytest.raises(project.BuildLockError, match="active build lock"),
    ):
        project_build.build_project(root)

    assert project.load_build_bundle(root).manifest.features is None


def test_read_build_bundle_holds_lock_for_consumer_lifetime(
    tmp_path: pathlib.Path,
) -> None:
    root = tmp_path / "project"
    copy_project_spec(root)
    shutil.copytree(example_support.example_bundle().root, root / project.BUILD_OUTPUT_DIR)
    built_bundle = project.load_build_bundle(root)

    with project.read_build_bundle(root) as bundle:
        assert bundle.root == built_bundle.root
        with pytest.raises(project.BuildLockError, match="active build lock"):
            project_build.build_project(root)

    assert project.load_build_bundle(root).manifest.features is None


def test_project_build_rejects_invalid_scope(tmp_path: pathlib.Path) -> None:
    root = tmp_path / "project"
    copy_project_spec(root)

    with pytest.raises(project.ProjectBuildError, match="at least one output feature"):
        project_build.build_project(root, features=[])
    with pytest.raises(project.ProjectBuildError, match="Unknown output feature"):
        project_build.build_project(root, features=["not-a-feature"])
    assert not (root / project.BUILD_OUTPUT_DIR).exists()


def test_project_build_missing_source(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, "--project-root", str(tmp_path))
    assert error.value.code == 1
    assert "Project build source loading failed: No spec source found" in capsys.readouterr().err
    assert not (tmp_path / project.GENERATED_DIR).exists()


def test_project_build_help(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["uptimely", "project", "build", "--help"])
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
        ["project"],
        ["project", "unknown"],
        [
            "project",
            "build",
            "--python-spec",
            "module:attribute",
            "--json-spec",
            "source.json",
        ],
        ["project", "build", "--output", "custom"],
        ["project", "build", "--features"],
        ["project", "build", "--verbose"],
        ["build", "--verbose"],
        ["spec", "feature-graph", "--verbose"],
    ],
)
def test_project_requires_valid_arguments(
    monkeypatch: pytest.MonkeyPatch, arguments: list[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["uptimely", *arguments])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2
