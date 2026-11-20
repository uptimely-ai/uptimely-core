import contextlib
import json
import pathlib
import shutil
import sys
import threading
from collections import abc
from concurrent import futures

import pytest
from support import examples as example_support

from uptimely import application, spec
from uptimely import plan as plan_module
from uptimely.build import builder as project_build
from uptimely.build import bundle, locking
from uptimely.cli import cli
from uptimely.codebase import packaging


def invoke(monkeypatch: pytest.MonkeyPatch, *arguments: str) -> None:
    monkeypatch.setattr(sys, "argv", ["uptimely", "build", *arguments])
    cli.main()


def copy_project_spec(root: pathlib.Path) -> pathlib.Path:
    bundle = example_support.example_bundle()
    source = root / application.SPEC_JSON_ENTRY_FILE
    source.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(bundle.spec_path, source)
    return source


def bundle_files(root: pathlib.Path) -> dict[str, bytes]:
    build_root = root / application.BUILD_OUTPUT_DIR
    return {
        path.relative_to(build_root).as_posix(): path.read_bytes()
        for path in build_root.rglob("*")
        if path.is_file()
    }


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

    project_build.build(root)

    assert len(compiled) == 1
    assert len(plans) == 1
    assert plans[0] is compiled[0]


def test_project_build_packages_python_source_and_requirements(
    tmp_path: pathlib.Path,
) -> None:
    root = tmp_path / "project"
    example_support.copy_example_project(root)
    requirements = b"polars>=1,<2\n"
    (root / "runtimes" / "python" / "requirements.txt").write_bytes(requirements)
    (root / "requirements.txt").write_text("unused-package\n", encoding="utf-8")
    (root / "poetry.lock").write_text("# development lock\n", encoding="utf-8")

    build = project_build.build(root)

    assert build.manifest.artifacts.model_dump()["packages"] == {
        "project": {"path": "packages/project", "runtime": "python"}
    }
    assert build.manifest.artifacts.runtimes == {"python": "runtimes/python/requirements.txt"}
    source = build.package_paths["project"]
    assert (source / "pump_analytics.py").is_file()
    assert build.runtime_paths["python"].read_bytes() == requirements
    assert not (build.root / "poetry.lock").exists()
    assert not (source / "__pycache__").exists()

    shutil.rmtree(root / "src")
    invocation = next(
        item for item in build.execution_plan.invocations if item.function_id == "pump_mode"
    )
    result = application.Uptimely(root).run(
        preview_rows=1, operator=(invocation.profile_id, invocation.operator_id)
    )

    assert result.failures == {}


def test_bundle_loader_requires_declared_requirements(tmp_path: pathlib.Path) -> None:
    root = tmp_path / "project"
    copy_project_spec(root)
    (root / "requirements.txt").touch()
    build = project_build.build(root)
    build.runtime_paths["python"].unlink()

    with pytest.raises(
        application.BuildError, match=r"missing artifact runtimes/python/requirements\.txt"
    ):
        application.load_build_bundle(root)


@pytest.mark.parametrize("override", [False, True])
def test_project_build_selects_runtimes_path(tmp_path: pathlib.Path, override: bool) -> None:
    copy_project_spec(tmp_path)
    (tmp_path / "uptimely.toml").write_text('[runtimes]\npath = "worker-env"\n', encoding="utf-8")
    runtime = tmp_path / "worker-env"
    runtime.mkdir()
    (runtime / "requirements.txt").write_bytes(b"polars>=1,<2\n")
    alternate = tmp_path / "alternate"
    alternate.mkdir()
    (alternate / "requirements.txt").write_bytes(b"polars==1.0.0\n")

    build = application.Uptimely(tmp_path).build(runtimes_path=alternate if override else None)

    assert build.runtime_paths["python"] == build.root / "runtimes" / "python" / "requirements.txt"
    expected_source = alternate if override else runtime
    expected_requirements = expected_source / "requirements.txt"
    assert build.runtime_paths["python"].read_bytes() == expected_requirements.read_bytes()


def test_bundle_loader_checks_code_runtime_reference(tmp_path: pathlib.Path) -> None:
    root = tmp_path / "project"
    example_support.copy_example_project(root)
    build = project_build.build(root)
    manifest_path = root / application.BUILD_MANIFEST_FILE
    manifest = build.manifest.model_dump()
    manifest["artifacts"]["packages"]["project"]["runtime"] = "missing"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(application.BuildError, match="refers to undeclared runtime 'missing'"):
        application.load_build_bundle(root)


def test_project_build_preserves_dependency_markers_in_generated_requirements(
    tmp_path: pathlib.Path,
) -> None:
    copy_project_spec(tmp_path)
    dependency = "package[extra]>=1; sys_platform == 'win32'"
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\ndependencies = ["{dependency}"]\n'
        '[project.optional-dependencies]\ntest = ["pytest"]\n',
        encoding="utf-8",
    )

    build = project_build.build(tmp_path)

    assert build.runtime_paths["python"].read_bytes() == f"{dependency}\n".encode()


def test_project_build_reports_invalid_dependency_metadata(tmp_path: pathlib.Path) -> None:
    copy_project_spec(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\ndependencies = "polars"\n', encoding="utf-8"
    )

    with pytest.raises(application.ProjectBuildError, match=r"\[project\]\.dependencies"):
        project_build.build(tmp_path)


def test_bundle_loader_requires_declared_python_source(
    tmp_path: pathlib.Path,
) -> None:
    root = tmp_path / "project"
    example_support.copy_example_project(root)
    build = project_build.build(root)
    shutil.rmtree(build.package_paths["project"])

    with pytest.raises(application.BuildError, match="missing artifact packages/project"):
        application.load_build_bundle(root)


def test_project_build_publishes_opaque_code_artifacts(tmp_path: pathlib.Path) -> None:
    class Packager:
        def stage(
            self,
            project_root: pathlib.Path,
            source: pathlib.Path,
            staging_root: pathlib.Path,
            runtimes_root: pathlib.Path,
        ) -> packaging.StagedCode:
            artifact = staging_root / "packages" / "bin" / "worker"
            artifact.parent.mkdir(parents=True)
            artifact.write_bytes(b"packaged implementation")
            other_package = staging_root / "packages" / "tools"
            other_package.mkdir()
            runtime = staging_root / "runtimes" / "native" / "runtime.json"
            runtime.parent.mkdir(parents=True)
            runtime.write_text("{}", encoding="utf-8")
            return packaging.StagedCode(
                packages={
                    "bin": packaging.CodePackage(path="packages/bin", runtime="native"),
                    "tools": packaging.CodePackage(path="packages/tools", runtime="native"),
                },
                runtimes={"native": "runtimes/native/runtime.json"},
            )

    spec_path = tmp_path / application.SPEC_JSON_ENTRY_FILE
    spec_path.parent.mkdir()
    spec.write_document(spec.Spec(), spec_path)
    project_build.ProjectBuilder(tmp_path, code_packager=Packager()).build()

    loaded = application.load_build_bundle(tmp_path)
    assert loaded.manifest.artifacts.model_dump()["packages"] == {
        "bin": {"path": "packages/bin", "runtime": "native"},
        "tools": {"path": "packages/tools", "runtime": "native"},
    }
    assert set(loaded.runtime_paths) == {"native"}
    assert (loaded.package_paths["bin"] / "worker").read_bytes() == b"packaged implementation"


@pytest.mark.parametrize("directory", ["packages", "runtimes"])
def test_project_build_rejects_loose_package_or_runtime_files(
    tmp_path: pathlib.Path, directory: str
) -> None:
    class Packager:
        def stage(
            self,
            project_root: pathlib.Path,
            source: pathlib.Path,
            staging_root: pathlib.Path,
            runtimes_root: pathlib.Path,
        ) -> packaging.StagedCode:
            target = staging_root / directory
            target.mkdir()
            (target / "loose.txt").touch()
            return packaging.StagedCode()

    copy_project_spec(tmp_path)
    with pytest.raises(
        application.ProjectBuildError,
        match=f"{directory}/ must contain only declared ID directories",
    ):
        project_build.ProjectBuilder(tmp_path, code_packager=Packager()).build()


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
    shutil.copytree(example_support.example_bundle().root, root / application.BUILD_OUTPUT_DIR)
    snapshot = root / application.EXPLORER_DATA_FILE
    previous_snapshot = snapshot.read_bytes()
    old_bundle = bundle_files(root)

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
    assert f"Build files created to {root / application.BUILD_OUTPUT_DIR}" not in result.out
    assert bundle_files(root) == old_bundle
    assert snapshot.read_bytes() == previous_snapshot
    assert not list((root / application.ARTIFACTS_DIR).glob(".build-staging-*"))
    assert not list((root / application.ARTIFACTS_DIR).glob(".build-backup-*"))


def test_explorer_snapshot_read_retries_during_bundle_replacement(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot = tmp_path / application.EXPLORER_DATA_FILE
    snapshot.parent.mkdir(parents=True)
    snapshot.write_bytes(b'{"build": "original"}')
    replacement = tmp_path / "replacement"
    replacement.mkdir()
    new_snapshot = b'{"build": "replacement"}'
    (replacement / snapshot.name).write_bytes(new_snapshot)
    read_reached_lock = threading.Event()
    original_lock = locking.build_lock

    def signal_read(
        root: str | pathlib.Path, *, exclusive: bool, wait: bool = True
    ) -> contextlib.AbstractContextManager[None]:
        read_reached_lock.set()
        return original_lock(root, exclusive=exclusive, wait=wait)

    with futures.ThreadPoolExecutor(max_workers=1) as executor:
        with original_lock(tmp_path, exclusive=True, wait=False):
            snapshot.parent.rename(tmp_path / "old-build")
            monkeypatch.setattr(locking, "build_lock", signal_read)
            read = executor.submit(bundle.BundleStore(tmp_path).read_explorer_snapshot)
            assert read_reached_lock.wait(timeout=5)
            replacement.rename(snapshot.parent)

        assert read.result(timeout=5) == new_snapshot


def test_bundle_loader_requires_declared_explorer_snapshot(tmp_path: pathlib.Path) -> None:
    copy_project_spec(tmp_path)
    build = project_build.build(tmp_path)
    assert build.explorer_path == tmp_path / application.EXPLORER_DATA_FILE
    build.explorer_path.unlink()

    with pytest.raises(application.BuildError, match=r"missing artifact explorer\.json"):
        application.load_build_bundle(tmp_path)


@pytest.mark.parametrize("exclusive", [False, True])
def test_project_build_fails_while_bundle_lock_is_held(
    tmp_path: pathlib.Path,
    exclusive: bool,
) -> None:
    root = tmp_path / "project"
    copy_project_spec(root)
    shutil.copytree(example_support.example_bundle().root, root / application.BUILD_OUTPUT_DIR)

    with (
        application.build_lock(root, exclusive=exclusive),
        pytest.raises(application.BuildLockError, match="active build lock"),
    ):
        project_build.build(root)

    assert application.load_build_bundle(root).manifest.features is None


def test_read_build_bundle_holds_lock_for_consumer_lifetime(
    tmp_path: pathlib.Path,
) -> None:
    root = tmp_path / "project"
    copy_project_spec(root)
    shutil.copytree(example_support.example_bundle().root, root / application.BUILD_OUTPUT_DIR)
    built_bundle = application.load_build_bundle(root)

    with application.read_build_bundle(root) as bundle:
        assert bundle.root == built_bundle.root
        with pytest.raises(application.BuildLockError, match="active build lock"):
            project_build.build(root)

    assert application.load_build_bundle(root).manifest.features is None
