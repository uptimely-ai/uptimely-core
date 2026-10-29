"""Pytest fixtures and lifecycle hooks for isolated test artifacts."""

import itertools
import pathlib
import tempfile

import pytest
from support import examples, execution

from uptimely import engine, execution_plan, project, spec


@pytest.fixture(scope="session")
def example_projects() -> pathlib.Path:
    """Prepare artifacts for tests that access example paths directly."""
    examples.prepare_example_projects(examples.EXAMPLES_ROOT)
    return examples.EXAMPLES_ROOT


@pytest.fixture
def example_bundle_factory(example_projects: pathlib.Path) -> examples.BundleFactory:
    """Load a fresh spec and plan on each call, including scoped examples."""
    return examples.example_bundle


@pytest.fixture
def pump_bundle(example_bundle_factory: examples.BundleFactory) -> project.BuildBundle:
    """Provide one independent pump bundle per test."""
    return example_bundle_factory()


@pytest.fixture
def example_project_factory(example_projects: pathlib.Path) -> examples.ProjectFactory:
    """Copy prepared example builds into paths owned by the requesting test."""
    return examples.copy_example_project


@pytest.fixture
def bundle_for_plan(tmp_path: pathlib.Path) -> execution.BundleFactory:
    """Create independent synthetic bundles under this test's temporary path."""
    identifiers = itertools.count()

    def create(
        execution_plan: execution_plan.ExecutionPlan,
        project_root: pathlib.Path | None = None,
        spec_definition: spec.Spec | None = None,
    ) -> project.BuildBundle:
        return execution.bundle_for_plan(
            execution_plan,
            project_root,
            spec_definition,
            build_root=tmp_path / f"bundle-{next(identifiers)}",
        )

    return create


@pytest.fixture
def engine_for_plan(bundle_for_plan: execution.BundleFactory) -> execution.EngineFactory:
    """Create engines whose synthetic bundle files belong to this test."""

    def create(
        execution_plan: execution_plan.ExecutionPlan,
        parameters: dict[str, object] | None = None,
        project_root: pathlib.Path | None = None,
        spec_definition: spec.Spec | None = None,
    ) -> engine.Engine:
        return engine.Engine(
            bundle_for_plan(execution_plan, project_root, spec_definition),
            engine.EngineConfig(),
            parameters,
        )

    return create


def pytest_configure(config: pytest.Config) -> None:
    """Reserve one session-owned shared directory before test collection."""
    if not hasattr(config, "workerinput"):
        root = tempfile.TemporaryDirectory(prefix="uptimely-core-tests-")
        config.add_cleanup(root.cleanup)
        patch = pytest.MonkeyPatch()
        config.add_cleanup(patch.undo)
        examples_root = pathlib.Path(root.name) / "examples"
        patch.setattr(examples, "EXAMPLES_ROOT", examples_root)
        patch.setenv("UPTIMELY_TEST_EXAMPLES_ROOT", str(examples_root))
    config.add_cleanup(examples.clear_caches)
