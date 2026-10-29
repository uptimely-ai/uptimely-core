"""Prepare and load isolated example artifacts for tests."""

import functools
import os
import pathlib
import shutil
import tempfile
import typing

from uptimely import compiler, execution_plan, spec
from uptimely import project as project_module

REPOSITORY_ROOT = pathlib.Path(__file__).parents[2]
EXAMPLES_ROOT = pathlib.Path(
    os.environ.get("UPTIMELY_TEST_EXAMPLES_ROOT", REPOSITORY_ROOT / "examples")
)


class BundleFactory(typing.Protocol):
    """Load independent mutable bundles from reusable example artifacts."""

    def __call__(
        self, example: str = "pump_analytics", features: tuple[str, ...] | None = None
    ) -> project_module.BuildBundle: ...


class ProjectFactory(typing.Protocol):
    """Copy reusable example artifacts to an isolated test project."""

    def __call__(
        self,
        target: pathlib.Path,
        example: str = "pump_analytics",
        features: tuple[str, ...] | None = None,
    ) -> pathlib.Path: ...


@functools.cache
def prepare_example_projects(examples_root: pathlib.Path) -> None:
    """Prepare shared examples once, including when workers start concurrently."""
    ready = examples_root.parent / ".examples-ready"
    with project_module.build_lock(examples_root.parent, exclusive=True):
        if ready.is_file():
            return
        shutil.copytree(
            REPOSITORY_ROOT / "examples",
            examples_root,
            ignore=shutil.ignore_patterns("_generated", "__pycache__"),
            dirs_exist_ok=True,
        )
        project_module.build_project(examples_root / "pump_analytics")
        ready.touch()


@functools.cache
def _example_project(example: str, features: tuple[str, ...] | None) -> pathlib.Path:
    """Prepare each scoped example once per worker; reuse full session builds."""
    prepare_example_projects(EXAMPLES_ROOT)
    source = EXAMPLES_ROOT / example
    if features is None:
        return source
    root = pathlib.Path(tempfile.mkdtemp(prefix="scoped-example-", dir=EXAMPLES_ROOT.parent))
    target = root / example
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("_generated", "__pycache__"))
    project_module.build_project(
        target,
        json_spec=source / project_module.BUILD_OUTPUT_DIR / "spec.json",
        features=features,
    )
    return target


def example_bundle(
    example: str = "pump_analytics", features: tuple[str, ...] | None = None
) -> project_module.BuildBundle:
    """Load fresh, mutable objects from a reusable example build."""
    return project_module.load_build_bundle(_example_project(example, features))


def copy_example_project(
    target: pathlib.Path,
    example: str = "pump_analytics",
    features: tuple[str, ...] | None = None,
) -> pathlib.Path:
    """Copy a prepared example, including its build, for an isolated test."""
    shutil.copytree(
        _example_project(example, features),
        target,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    return target


def plan_for_spec(spec_definition: spec.Spec) -> execution_plan.ExecutionPlan:
    """Reuse saved example plans; compile only new or modified specifications."""
    bundle = example_bundle("pump_analytics")
    if spec_definition == bundle.spec_definition:
        return bundle.execution_plan
    return compiler.Compiler().compile(spec_definition)


def clear_caches() -> None:
    """Release cached paths when their owning pytest session ends."""
    prepare_example_projects.cache_clear()
    _example_project.cache_clear()
