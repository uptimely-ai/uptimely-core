"""Verify that reusable example artifacts preserve per-test isolation."""

import pathlib
from concurrent import futures

import pytest
from support import examples as example_support
from support import rendering as rendering_support

from uptimely import compiler, execution_plan, project, spec


def test_example_setup_reuses_artifacts_without_building_or_compiling(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = example_support.example_bundle()

    def unexpected_work(*args: object, **kwargs: object) -> None:
        pytest.fail("Unchanged example setup must reuse saved artifacts")

    monkeypatch.setattr(compiler.Compiler, "compile", unexpected_work)
    monkeypatch.setattr(project, "build_project", unexpected_work)
    plan = example_support.plan_for_spec(bundle.spec_definition)
    copied_root = example_support.copy_example_project(tmp_path / "project")

    assert execution_plan.to_dict(plan) == execution_plan.to_dict(bundle.execution_plan)
    assert project.load_build_bundle(copied_root).manifest == bundle.manifest
    assert rendering_support.render_explorer(
        bundle.spec_definition, tmp_path / "site/index.html"
    ).is_file()


def test_example_objects_and_project_copies_are_independent(tmp_path: pathlib.Path) -> None:
    first = example_support.example_bundle()
    second = example_support.example_bundle()
    original_plan = execution_plan.to_dict(second.execution_plan)
    first.spec_definition.name = "Changed by one test"
    first.execution_plan.invocations[0].arguments["test_only"] = True
    copied_root = example_support.copy_example_project(tmp_path / "project")
    copied = project.load_build_bundle(copied_root)
    copied.spec_path.write_text("changed by one test", encoding="utf-8")

    assert second.spec_definition.name != first.spec_definition.name
    assert execution_plan.to_dict(second.execution_plan) == original_plan
    assert execution_plan.to_dict(example_support.example_bundle().execution_plan) == original_plan
    assert spec.load_spec(first.spec_path).name == second.spec_definition.name


def test_scoped_example_is_built_once_for_multiple_consumers(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, example_projects: pathlib.Path
) -> None:
    features = ("bearing_temperature_max",)
    original_build = project.build_project
    build_calls = 0

    def build(
        project_root: pathlib.Path,
        *,
        json_spec: pathlib.Path,
        features: tuple[str, ...],
    ) -> project.BuildBundle:
        nonlocal build_calls
        build_calls += 1
        return original_build(project_root, json_spec=json_spec, features=features)

    monkeypatch.setattr(project, "build_project", build)

    first = example_support.example_bundle(features=features)
    second = example_support.example_bundle(features=features)
    copied_root = example_support.copy_example_project(
        tmp_path / "scoped project", features=features
    )

    assert build_calls == 1
    assert first.execution_plan is not second.execution_plan
    assert project.load_build_bundle(copied_root).manifest.features == list(features)


def test_modified_example_is_compiled_instead_of_using_stale_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = example_support.example_bundle()
    definition = bundle.spec_definition
    definition.name = "Modified example"
    compiled_specs: list[spec.Spec] = []

    def compile_spec(
        self: compiler.Compiler,
        spec_definition: spec.Spec,
        features: list[str] | None = None,
    ) -> execution_plan.ExecutionPlan:
        compiled_specs.append(spec_definition)
        return bundle.execution_plan

    monkeypatch.setattr(compiler.Compiler, "compile", compile_spec)

    assert example_support.plan_for_spec(definition) is bundle.execution_plan
    assert compiled_specs == [definition]


def test_render_uses_supplied_custom_plan_without_compiling(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = example_support.example_bundle()
    bundle.spec_definition.name = "Custom rendering"

    def unexpected_compile(
        self: compiler.Compiler,
        spec_definition: spec.Spec,
        features: list[str] | None = None,
    ) -> execution_plan.ExecutionPlan:
        pytest.fail("An explicitly supplied plan must not be compiled again")

    monkeypatch.setattr(compiler.Compiler, "compile", unexpected_compile)

    assert rendering_support.render_explorer(
        bundle.spec_definition, tmp_path / "index.html", plan=bundle.execution_plan
    ).is_file()


def test_shared_examples_are_built_once_under_concurrent_requests(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    examples_root = tmp_path / "examples"
    builds: list[pathlib.Path] = []
    monkeypatch.setattr(project, "build_project", builds.append)

    with futures.ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(example_support.prepare_example_projects, [examples_root] * 4))
    example_support.prepare_example_projects.cache_clear()
    example_support.prepare_example_projects(examples_root)

    assert builds == [examples_root / "pump_analytics"]
    assert (examples_root / "pump_analytics/spec").is_dir()


def test_failed_example_build_can_be_retried(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    examples_root = tmp_path / "examples"

    def fail_build(project_root: pathlib.Path) -> None:
        raise RuntimeError("Example build failed")

    monkeypatch.setattr(project, "build_project", fail_build)
    with pytest.raises(RuntimeError, match="Example build failed"):
        example_support.prepare_example_projects(examples_root)
    assert not (tmp_path / ".examples-ready").exists()

    builds: list[pathlib.Path] = []
    monkeypatch.setattr(project, "build_project", builds.append)
    example_support.prepare_example_projects(examples_root)

    assert builds == [examples_root / "pump_analytics"]
    assert (tmp_path / ".examples-ready").is_file()
