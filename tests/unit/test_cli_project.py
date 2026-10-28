"""Tests for building and publishing project bundles without executing workflows."""

import json
import os
import pathlib
import shutil
import subprocess
import sys
from collections import abc

import pytest
from conftest import EXAMPLES_ROOT, copy_example_project, example_bundle

from uptimely import execution_plan as plan_module
from uptimely import project, spec
from uptimely.cli import cli
from uptimely.compiler import compiler as compiler_module
from uptimely.explorer import explorer as explorer_module
from uptimely.project.build import builder as project_build

REPOSITORY_ROOT = pathlib.Path(__file__).parents[2]
PUMP_SPEC_JSON = EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json"


def invoke(monkeypatch: pytest.MonkeyPatch, *arguments: str) -> None:
    monkeypatch.setattr(sys, "argv", ["uptimely", "project", "build", *arguments])
    cli.main()


def copy_project_spec(root: pathlib.Path) -> pathlib.Path:
    source = root / project.SPEC_JSON_ENTRY_FILE
    source.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PUMP_SPEC_JSON, source)
    return source


def bundle_files(root: pathlib.Path) -> dict[str, bytes]:
    build_root = root / project.BUILD_OUTPUT_DIR
    return {
        path.relative_to(build_root).as_posix(): path.read_bytes()
        for path in build_root.rglob("*")
        if path.is_file()
    }


@pytest.mark.parametrize(
    "verbose",
    [False, True],
)
@pytest.mark.parametrize("explicit_root", [False, True])
@pytest.mark.parametrize("empty_generated", [False, True])
def test_project_build_examples(
    tmp_path: pathlib.Path,
    verbose: bool,
    explicit_root: bool,
    empty_generated: bool,
) -> None:
    examples = tmp_path / "examples"
    examples.mkdir()
    shutil.copyfile(REPOSITORY_ROOT / "examples/__init__.py", examples / "__init__.py")
    root = examples / "pump_analytics"
    shutil.copytree(
        REPOSITORY_ROOT / "examples" / "pump_analytics",
        root,
        ignore=shutil.ignore_patterns("_generated", "__pycache__"),
    )
    if empty_generated:
        (root / project.GENERATED_DIR).mkdir()
    arguments = ["--project-root", str(root)] if explicit_root else []
    if verbose:
        arguments.append("--verbose")
    executable = shutil.which("uptimely")
    assert executable is not None, "The installed uptimely console script is required"
    command = [executable, "project", "build", *arguments]
    cwd = tmp_path if explicit_root else root
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    result = subprocess.run(
        command, cwd=cwd, env=environment, capture_output=True, text=True, timeout=90
    )

    assert result.returncode == 0, result.stderr
    assert not result.stderr
    if verbose:
        assert result.stdout.startswith("\n\nBuild\n")
        assert "  Build scope: all features\n" in result.stdout
        source = REPOSITORY_ROOT / "examples" / "pump_analytics" / project.SPEC_PYTHON_ENTRY_FILE
        assert f"  Spec source file: {source}\n" in result.stdout
        assert "Build files created to" not in result.stdout
    else:
        assert result.stdout == f"Build files created to {root / project.BUILD_OUTPUT_DIR}\n"
    bundle = project.load_build_bundle(root)
    assert bundle.manifest.features is None
    assert spec.load_spec(bundle.spec_path).entities
    assert bundle.execution_plan.invocations
    assert (bundle.explorer_path / "index.html").is_file()


def test_project_rebuild_replaces_previous_bundle(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = copy_example_project(tmp_path / "examples" / "pump_analytics")
    (root.parent / "__init__.py").write_text("", encoding="utf-8")
    bundle = project.load_build_bundle(root)
    old_plan = bundle.execution_plan
    old_spec = bundle.spec_path.read_bytes()
    stale_file = bundle.explorer_path / "stale.html"
    stale_file.write_text("stale", encoding="utf-8")

    invoke(monkeypatch, "--project-root", str(root))

    rebuilt_bundle = project.load_build_bundle(root)
    assert rebuilt_bundle.spec_path.read_bytes() == old_spec
    assert {item.id: item for item in rebuilt_bundle.execution_plan.invocations} == {
        item.id: item for item in old_plan.invocations
    }
    assert len(rebuilt_bundle.execution_plan.execution_stages) == len(old_plan.execution_stages)
    assert not (rebuilt_bundle.explorer_path / "stale.html").exists()
    assert not (root / "_generated/spec/spec.json").exists()
    assert not (root / "_generated/compile/execution_plan.json").exists()


@pytest.mark.parametrize("source_kind", ["entrypoint", "json"])
@pytest.mark.parametrize("verbose", [False, True])
def test_project_build_explicit_source_does_not_execute_workflow(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    source_kind: str,
    verbose: bool,
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
                "spec_version": 2,
                "name": "Build-only test",
                "functions": {
                    "read": {
                        "kind": "read",
                        "entrypoint": "build_functions:read",
                        "returns": "dataframe",
                    }
                },
                "entities": {
                    "example": {
                        "name": "Example",
                        "datasets": {
                            "values": {
                                "features": {"value": {}},
                                "mappings": {
                                    "read": {
                                        "binding": {"function": "read"},
                                        "features": {"outputs": ["$features.value"]},
                                    }
                                },
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
            "from uptimely.spec.python import Dataset, Entity, Feature, FunctionMapping\n"
            "import build_functions\n"
            "example = Entity(id='example', name='Example', dimensions=[])\n"
            "class Values(Dataset):\n"
            "    id = 'values'\n"
            "    entity = example\n"
            "    read = FunctionMapping(\n"
            "        function=api.ref.function(build_functions.read, kind='read'),\n"
            "        arguments={},\n"
            "        outputs=[Feature(name='value')],\n"
            "    )\n"
            "definition = api.PythonSpec(dimensions=[], entities=[example], datasets=[Values])\n",
            encoding="utf-8",
        )
        arguments = ["--python-spec", "declaration:definition"]
    else:
        arguments = ["--json-spec", "source.json"]

    if verbose:
        arguments.append("--verbose")
    invoke(monkeypatch, "--project-root", str(root), *arguments)

    bundle = project.load_build_bundle(root)
    result = capsys.readouterr()
    assert not result.err
    if verbose:
        source_file = root / "declaration.py" if source_kind != "json" else source
        assert f"  Spec source file: {source_file}\n" in result.out
        assert "  Number of functions: 1\n" in result.out
        assert "  Number of datasets: 1\n" in result.out
        assert "  Number of features: 1\n" in result.out
    else:
        assert result.out == f"Build files created to {bundle.root}\n"
    assert spec.load_spec(bundle.spec_path).entities
    assert bundle.execution_plan.invocations
    assert (bundle.explorer_path / "index.html").exists()
    assert not (root / "_generated/spec").exists()
    assert not (root / project.EXPLORER_OUTPUT_DIR).exists()


@pytest.mark.parametrize("scoped", [False, True])
def test_project_build_verbose_summary(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    scoped: bool,
) -> None:
    root = tmp_path / "project"
    source = copy_project_spec(root)
    definition = spec.load_spec(source)
    datasets = [
        dataset for entity in definition.entities.values() for dataset in entity.datasets.values()
    ]
    times = iter([10.0, 11.234])
    monkeypatch.setattr(cli.project.time, "perf_counter", lambda: next(times))
    arguments = ["--features", "pump_health_score"] if scoped else []

    invoke(monkeypatch, "--project-root", str(root), "--verbose", *arguments)

    bundle = project.load_build_bundle(root)
    result = capsys.readouterr()
    scope = "pump_health_score" if scoped else "all features"
    assert not result.err
    assert result.out == (
        "\n\nBuild\n"
        "  Duration: 1.234 s\n"
        f"  Output folder: {bundle.root}\n"
        f"  Build scope: {scope}\n"
        "\nSpec\n"
        f"  Spec source file: {source}\n"
        f"  Number of functions: {len(definition.functions)}\n"
        f"  Number of datasets: {len(datasets)}\n"
        f"  Number of features: {sum(len(dataset.features) for dataset in datasets)}\n"
        "\nPlan\n"
        f"  Number of stages: {len(bundle.execution_plan.stages)}\n"
        f"  Number of invocations: {len(bundle.execution_plan.invocations)}\n"
    )


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
        f"Build warning\nBuild files created to {root / project.BUILD_OUTPUT_DIR}\n"
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
    sinks = [invocation for invocation in plan_invocations if invocation.operation == "write"]
    assert sinks
    plan_ids = {invocation.id for invocation in plan_invocations}
    produced_features = {
        feature for invocation in plan_invocations for feature in invocation.output_features
    }
    dimensions = set(source_spec.dimensions)
    for entity in source_spec.entities.values():
        dimensions.update(entity.dimension_ids)
    for invocation in plan_invocations:
        assert set(invocation.dependency_ids) <= plan_ids
    for sink in sinks:
        assert set(sink.input_features) <= produced_features | dimensions
    full_plan = example_bundle().execution_plan
    assert len(bundle.execution_plan.invocations) <= len(full_plan.invocations)
    assert len({invocation.id for invocation in bundle.execution_plan.invocations}) == len(
        bundle.execution_plan.invocations
    )
    full_bundle = project_build.build_project(root)
    assert full_bundle.manifest.features is None


def test_project_build_compiles_once_and_renders_the_compiled_plan(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "project"
    copy_project_spec(root)
    plans: list[plan_module.ExecutionPlan] = []
    compiled: list[plan_module.ExecutionPlan] = []
    original_compile = project_build.compiler.Compiler.compile
    original_create_html = explorer_module.Explorer.create_html

    def compile_once(
        self: project_build.compiler.Compiler,
        spec_definition: spec.Spec,
        features: abc.Collection[str] | None = None,
    ) -> plan_module.ExecutionPlan:
        compiled_plan = original_compile(self, spec_definition, features)
        compiled.append(compiled_plan)
        return compiled_plan

    def render_compiled_plan(
        self: explorer_module.Explorer, *args: object, **kwargs: object
    ) -> pathlib.Path:
        assert self.plan is not None
        plans.append(self.plan)
        return original_create_html(self, *args, **kwargs)

    monkeypatch.setattr(project_build.compiler.Compiler, "compile", compile_once)
    monkeypatch.setattr(explorer_module.Explorer, "create_html", render_compiled_plan)

    project_build.build_project(root)

    assert len(compiled) == 1
    assert len(plans) == 1
    assert plans[0] is compiled[0]


@pytest.mark.parametrize(
    ("stage", "expected"),
    [
        ("compile", "Project build compilation failed"),
        ("render", "Project build artifact generation failed"),
        ("publish", "Project build publication failed"),
    ],
)
@pytest.mark.parametrize("verbose", [False, True])
def test_project_build_failures_preserve_previous_bundle(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stage: str,
    expected: str,
    verbose: bool,
) -> None:
    root = tmp_path / "project"
    copy_project_spec(root)
    shutil.copytree(example_bundle().root, root / project.BUILD_OUTPUT_DIR)
    old_bundle = bundle_files(root)

    if stage == "compile":

        def fail_compile(
            self: object,
            spec_definition: spec.Spec,
            features: abc.Collection[str] | None = None,
        ) -> None:
            raise ValueError("Injected compile failure")

        monkeypatch.setattr(project_build.compiler.Compiler, "compile", fail_compile)
    elif stage == "render":

        def fail_render(self: object, *args: object, **kwargs: object) -> pathlib.Path:
            raise OSError("Injected renderer failure")

        monkeypatch.setattr(explorer_module.Explorer, "create_html", fail_render)
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
        arguments = ["--verbose"] if verbose else []
        invoke(monkeypatch, "--project-root", str(root), *arguments)

    assert error.value.code == 1
    result = capsys.readouterr()
    assert expected in result.err
    assert not result.out
    assert bundle_files(root) == old_bundle
    assert not list((root / project.GENERATED_DIR).glob(".build-staging-*"))
    assert not list((root / project.GENERATED_DIR).glob(".build-backup-*"))


@pytest.mark.parametrize("exclusive", [False, True])
def test_project_build_fails_while_bundle_lock_is_held(
    tmp_path: pathlib.Path,
    exclusive: bool,
) -> None:
    root = tmp_path / "project"
    copy_project_spec(root)
    shutil.copytree(example_bundle().root, root / project.BUILD_OUTPUT_DIR)

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
    shutil.copytree(example_bundle().root, root / project.BUILD_OUTPUT_DIR)
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
    assert "--verbose" in result.out
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
    ],
)
def test_project_requires_valid_arguments(
    monkeypatch: pytest.MonkeyPatch, arguments: list[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["uptimely", *arguments])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2
