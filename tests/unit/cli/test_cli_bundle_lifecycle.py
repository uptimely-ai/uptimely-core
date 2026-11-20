import pathlib
import shutil
import sys
import threading
from collections import abc

import pytest
from support import examples as example_support

from uptimely import application, spec
from uptimely import plan as plan_module
from uptimely.build import builder as project_build
from uptimely.cli import cli


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
    old_bundle = bundle_files(root)
    snapshot = root / application.EXPLORER_DATA_FILE
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
    assert f"Build files created to {root / application.BUILD_OUTPUT_DIR}" not in result.out
    assert bundle_files(root) == old_bundle
    assert snapshot.read_text(encoding="utf-8") == "previous snapshot"
    assert not list((root / application.ARTIFACTS_DIR).glob(".build-staging-*"))
    assert not list((root / application.ARTIFACTS_DIR).glob(".build-backup-*"))


def test_snapshot_publication_failure_preserves_previous_snapshot(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "project"
    copy_project_spec(root)
    snapshot = root / application.EXPLORER_DATA_FILE
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text("previous snapshot", encoding="utf-8")
    original_replace = project_build.os.replace

    def fail_snapshot_replace(source: pathlib.Path, target: pathlib.Path) -> None:
        if target == snapshot:
            raise OSError("injected snapshot failure")
        original_replace(source, target)

    monkeypatch.setattr(project_build.os, "replace", fail_snapshot_replace)

    with pytest.raises(application.ProjectBuildError, match="Explorer snapshot publication failed"):
        project_build.build(root)

    assert application.load_build_bundle(root).manifest.build_version == application.BUILD_VERSION
    assert snapshot.read_text(encoding="utf-8") == "previous snapshot"
    assert not list(snapshot.parent.glob(f".{snapshot.name}.*.tmp"))


def test_snapshot_readers_observe_complete_old_or_new_data(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = tmp_path / application.EXPLORER_DATA_FILE
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
        target=project_build.ProjectBuilder(tmp_path)._publish_explorer_snapshot,
        args=(replacement,),
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
