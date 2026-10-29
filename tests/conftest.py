"""Isolate generated example builds using the installed example packages."""

import functools
import os
import pathlib
import shutil
import tempfile

import polars as pl
import pytest

from uptimely import compiler, execution_plan, spec
from uptimely import engine as engine_module
from uptimely import project as project_module
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
def _prepare_example_projects(examples_root: pathlib.Path) -> None:
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


@pytest.fixture(scope="session")
def example_projects() -> pathlib.Path:
    """Prepare artifacts for tests that access example paths directly."""
    _prepare_example_projects(EXAMPLES_ROOT)
    return EXAMPLES_ROOT


@functools.cache
def _example_project(example: str, features: tuple[str, ...] | None) -> pathlib.Path:
    """Prepare each scoped example once per worker; reuse full session builds."""
    _prepare_example_projects(EXAMPLES_ROOT)
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


def plan_for_spec(spec_definition: spec.Spec) -> execution_plan.ExecutionPlan:
    """Reuse saved example plans; compile only new or modified specifications."""
    bundle = example_bundle("pump_analytics")
    if spec_definition == bundle.spec_definition:
        return bundle.execution_plan
    return compiler.Compiler().compile(spec_definition)


def read_observation_totals() -> pl.DataFrame:
    """Load the small dataset used by the observation-totals spec fixture."""
    return pl.DataFrame(
        {
            "id": [1, 2],
            "input_1": [1, 3],
            "input_2": [2, 4],
        }
    )


def sum_observation_features(
    dataset: pl.LazyFrame,
    left_feature: str,
    right_feature: str,
    output: str,
) -> pl.LazyFrame:
    """Add two selected features for the observation-totals spec fixture."""
    return dataset.with_columns((pl.col(left_feature) + pl.col(right_feature)).alias(output))


def _spec_for_plan(execution_plan: execution_plan.ExecutionPlan) -> spec_model.Spec:
    """Create a minimal runtime spec for tests using hand-authored plans."""
    resources = execution_plan.resources
    dimensions = {
        identifier: definition or {"type": "string"}
        for identifier, definition in resources.get("dimensions", {}).items()
    }
    entities = dict(resources.get("entities", {}))
    functions = dict(resources.get("functions", {}))

    for invocation in execution_plan.invocations:
        entity = entities.setdefault(invocation.entity_id, {"dimensions": []})
        for dimension_id in entity.get("dimensions", []):
            dimensions.setdefault(dimension_id, {"type": "string"})
        function = functions.setdefault(invocation.function_id, {})
        function.setdefault("kind", invocation.function_kind)
        function.setdefault(
            "returns",
            {"escape": "any", "write": "none"}.get(invocation.function_kind, "dataframe"),
        )
        function.setdefault("entrypoint", invocation.entrypoint)
        function.setdefault("args", {})
        entity.setdefault("name", invocation.entity_id)
        entity.setdefault("datasets", {}).setdefault(invocation.dataset_id, {})

    return spec_model.Spec.model_validate(
        {
            "dimensions": dimensions,
            "functions": functions,
            "entities": entities,
        }
    )


def bundle_for_plan(
    execution_plan: execution_plan.ExecutionPlan,
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
    execution_plan: execution_plan.ExecutionPlan,
    parameters: dict[str, object] | None = None,
    project_root: pathlib.Path | None = None,
    spec_definition: spec.Spec | None = None,
) -> engine_module.Engine:
    """Create an engine for a plan using test runtime defaults."""
    return engine_module.Engine(
        bundle_for_plan(execution_plan, project_root, spec_definition),
        engine_module.EngineConfig(),
        parameters,
    )


def render_explorer(
    spec_definition: spec.Spec,
    output_path: str | pathlib.Path | None = None,
    include_generated_at: bool = False,
    *,
    plan: execution_plan.ExecutionPlan | None = None,
) -> pathlib.Path:
    """Render with a supplied or reusable plan, compiling only custom specs."""
    if plan is None:
        plan = plan_for_spec(spec_definition)
    return explorer.Explorer(spec_definition, plan=plan).create_html(
        output_path, include_generated_at
    )


def pytest_configure(config: pytest.Config) -> None:
    """Reserve a shared location without copying or building examples."""
    global EXAMPLES_ROOT, _TEST_ROOT

    if hasattr(config, "workerinput"):
        return

    _TEST_ROOT = pathlib.Path(tempfile.mkdtemp(prefix="uptimely-core-tests-"))
    EXAMPLES_ROOT = _TEST_ROOT / "examples"
    os.environ["UPTIMELY_TEST_EXAMPLES_ROOT"] = str(EXAMPLES_ROOT)


def pytest_unconfigure(config: pytest.Config) -> None:
    """Remove the isolated example projects created for this test run."""
    _prepare_example_projects.cache_clear()
    _example_project.cache_clear()
    for path in _TEMP_ROOTS:
        shutil.rmtree(path)
    if not hasattr(config, "workerinput") and _TEST_ROOT is not None:
        shutil.rmtree(_TEST_ROOT)
        if _ORIGINAL_EXAMPLES_ROOT is None:
            os.environ.pop("UPTIMELY_TEST_EXAMPLES_ROOT", None)
        else:
            os.environ["UPTIMELY_TEST_EXAMPLES_ROOT"] = _ORIGINAL_EXAMPLES_ROOT
