"""Verify that reusable example artifacts preserve per-test isolation."""

import pathlib
from concurrent import futures

import pytest
from support import examples as example_support
from support import execution as execution_support
from support import rendering as rendering_support

from uptimely import compiler, execution_plan, project, spec


def test_synthetic_bundle_factory_uses_independent_test_owned_directories(
    tmp_path: pathlib.Path,
    pump_bundle: project.BuildBundle,
    bundle_for_plan: execution_support.BundleFactory,
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    first = bundle_for_plan(pump_bundle.execution_plan, spec_definition=pump_bundle.spec_definition)
    second = bundle_for_plan(
        pump_bundle.execution_plan, spec_definition=pump_bundle.spec_definition
    )
    engine = engine_for_plan(
        pump_bundle.execution_plan, spec_definition=pump_bundle.spec_definition
    )

    assert first.root != second.root
    assert first.root.parent == second.root.parent == tmp_path
    assert first.spec_path.is_file()
    assert second.spec_path.is_file()
    assert engine.plan is pump_bundle.execution_plan
    assert len(list(tmp_path.glob("bundle-*/spec.json"))) == 3


def test_pump_bundle_is_reused_within_test_and_not_shared_with_factory_results(
    request: pytest.FixtureRequest,
    pump_bundle: project.BuildBundle,
    example_bundle_factory: example_support.BundleFactory,
) -> None:
    original_name = pump_bundle.spec_definition.name
    pump_bundle.spec_definition.name = "Changed fixture"
    pump_bundle.execution_plan.invocations[0].arguments["test_only"] = True

    assert request.getfixturevalue("pump_bundle") is pump_bundle
    independent = example_bundle_factory()
    assert independent.spec_definition.name == original_name
    assert "test_only" not in independent.execution_plan.invocations[0].arguments


@pytest.mark.parametrize("features", [None, ("health_signal_normalized",)])
def test_example_factories_return_independent_bundles_and_project_copies(
    tmp_path: pathlib.Path,
    features: tuple[str, ...] | None,
    example_bundle_factory: example_support.BundleFactory,
    example_project_factory: example_support.ProjectFactory,
) -> None:
    first = example_bundle_factory(features=features)
    second = example_bundle_factory(features=features)
    copied_root = example_project_factory(tmp_path / "copied project", features=features)
    copied = project.load_build_bundle(copied_root)
    copied.spec_path.write_text("test-only change", encoding="utf-8")
    first.spec_definition.name = "Changed bundle"
    first.execution_plan.invocations[0].arguments["test_only"] = True

    assert second.spec_definition.name != first.spec_definition.name
    assert "test_only" not in second.execution_plan.invocations[0].arguments
    assert spec.load_spec(second.spec_path).name == second.spec_definition.name
    assert copied.manifest.features == (list(features) if features is not None else None)


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
