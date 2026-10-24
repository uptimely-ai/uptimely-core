"""Isolate generated example builds using the installed example packages."""

import functools
import os
import pathlib
import shutil
import tempfile

import pytest

from uptimely import compiler, spec
from uptimely import engine as engine_module
from uptimely import project as project_module
from uptimely.compiler import plan as plan_module
from uptimely.explorer import explorer
from uptimely.spec import model as spec_model

REPOSITORY_ROOT = pathlib.Path(__file__).parent.parent
EXAMPLES_ROOT = pathlib.Path(
    os.environ.get("UPTIMELY_TEST_EXAMPLES_ROOT", REPOSITORY_ROOT / "examples")
)
_ORIGINAL_EXAMPLES_ROOT = os.environ.get("UPTIMELY_TEST_EXAMPLES_ROOT")
_TEST_ROOT: pathlib.Path | None = None
_TEMP_ROOTS: list[pathlib.Path] = []


@functools.cache
def _example_project(example: str, features: tuple[str, ...] | None) -> pathlib.Path:
    """Prepare each scoped example once per worker; reuse full session builds."""
    source = EXAMPLES_ROOT / example
    if features is None:
        return source
    root = pathlib.Path(tempfile.mkdtemp(prefix="uptimely-test-example-"))
    _TEMP_ROOTS.append(root)
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


def plan_for_spec(spec_definition: spec.Spec) -> plan_module.ExecutionPlan:
    """Reuse saved example plans; compile only new or modified specifications."""
    for example in ("pump_analytics", "simple_analytics"):
        bundle = example_bundle(example)
        if spec_definition == bundle.spec_definition:
            return bundle.execution_plan
    return compiler.Compiler(spec_definition).compile()


def _spec_for_plan(execution_plan: plan_module.ExecutionPlan) -> spec_model.Spec:
    """Create a minimal runtime spec for tests using hand-authored plans."""
    resources = execution_plan.plan.resources
    dimensions = {
        identifier: definition or {"type": "string"}
        for identifier, definition in resources.get("dimensions", {}).items()
    }
    entities = dict(resources.get("entities", {}))
    functions = dict(resources.get("functions", {}))

    for callable in execution_plan.callables:
        entity = entities.setdefault(callable.entity_id, {"dimensions": []})
        for dimension_id in entity.get("dimensions", []):
            dimensions.setdefault(dimension_id, {"type": "string"})
        function = functions.setdefault(callable.function_id, {})
        function.setdefault("operation", callable.operation)
        function.setdefault(
            "returns",
            {"escape": "any", "write": "none"}.get(callable.operation, "dataframe"),
        )
        function.setdefault("entrypoint", callable.entrypoint)
        function.setdefault("args", {})
        entity.setdefault("name", callable.entity_id)
        entity.setdefault("datasets", {}).setdefault(callable.dataset_id, {})

    return spec_model.Spec.model_validate(
        {
            "dimensions": dimensions,
            "functions": functions,
            "entities": entities,
        }
    )


def bundle_for_plan(
    execution_plan: plan_module.ExecutionPlan,
    project_root: pathlib.Path | None = None,
    spec_definition: spec.Spec | None = None,
) -> project_module.BuildBundle:
    """Wrap a plan in a test bundle for engine execution."""
    root = (project_root or REPOSITORY_ROOT).resolve()
    build_root = pathlib.Path(tempfile.mkdtemp(prefix="uptimely-test-plan-"))
    _TEMP_ROOTS.append(build_root)
    bundle_spec = spec_definition or _spec_for_plan(execution_plan)
    spec.write_document(bundle_spec, build_root / "spec.json")
    return project_module.BuildBundle(
        project_root=root,
        root=build_root,
        manifest=project_module.BuildManifest(
            build_version=project_module.BUILD_VERSION,
            uptimely_version="test",
            features=None,
            artifacts=project_module.BuildArtifactPaths(
                spec="spec.json",
                execution_plan="execution_plan.json",
                explorer="explorer",
            ),
            explorer_files=["index.html"],
        ),
        spec_path=build_root / "spec.json",
        spec_definition=bundle_spec,
        execution_plan_path=build_root / "execution_plan.json",
        explorer_path=build_root / "explorer",
        execution_plan=execution_plan,
    )


def engine_for_plan(
    execution_plan: plan_module.ExecutionPlan,
    bind: dict[str, dict[str, dict[str, object]]] | None = None,
    project_root: pathlib.Path | None = None,
    spec_definition: spec.Spec | None = None,
) -> engine_module.Engine:
    """Create an engine for a plan using test runtime defaults."""
    return engine_module.Engine(
        bundle_for_plan(execution_plan, project_root, spec_definition),
        engine_module.EngineConfig(bind=bind or {}),
    )


def render_explorer(
    spec_definition: spec.Spec,
    output_path: str | pathlib.Path | None = None,
    include_generated_at: bool = False,
    *,
    plan: plan_module.ExecutionPlan | None = None,
) -> pathlib.Path:
    """Render with a supplied or reusable plan, compiling only custom specs."""
    if plan is None:
        plan = plan_for_spec(spec_definition)
    return explorer.Explorer(spec_definition, plan=plan).create_html(
        output_path, include_generated_at
    )


def pytest_configure(config: pytest.Config) -> None:
    """Build example bundles required by tests that exercise saved artifacts."""
    global EXAMPLES_ROOT, _TEST_ROOT

    if hasattr(config, "workerinput"):
        return

    _TEST_ROOT = pathlib.Path(tempfile.mkdtemp(prefix="uptimely-core-tests-"))
    EXAMPLES_ROOT = _TEST_ROOT / "examples"
    shutil.copytree(
        REPOSITORY_ROOT / "examples",
        EXAMPLES_ROOT,
        ignore=shutil.ignore_patterns("_generated", "__pycache__"),
    )
    os.environ["UPTIMELY_TEST_EXAMPLES_ROOT"] = str(EXAMPLES_ROOT)

    for example in ("pump_analytics", "simple_analytics"):
        project_module.build_project(EXAMPLES_ROOT / example)


def pytest_unconfigure(config: pytest.Config) -> None:
    """Remove the isolated example projects created for this test run."""
    for path in _TEMP_ROOTS:
        shutil.rmtree(path)
    if not hasattr(config, "workerinput") and _TEST_ROOT is not None:
        shutil.rmtree(_TEST_ROOT)
        if _ORIGINAL_EXAMPLES_ROOT is None:
            os.environ.pop("UPTIMELY_TEST_EXAMPLES_ROOT", None)
        else:
            os.environ["UPTIMELY_TEST_EXAMPLES_ROOT"] = _ORIGINAL_EXAMPLES_ROOT
