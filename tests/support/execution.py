"""Construct test bundles and engines from hand-authored plans."""

import pathlib
import typing

from uptimely import engine as engine_module
from uptimely import execution_plan, spec
from uptimely import project as project_module
from uptimely.spec import model as spec_model

REPOSITORY_ROOT = pathlib.Path(__file__).parents[2]


class BundleFactory(typing.Protocol):
    """Create synthetic bundles in test-owned temporary directories."""

    def __call__(
        self,
        execution_plan: execution_plan.ExecutionPlan,
        project_root: pathlib.Path | None = None,
        spec_definition: spec.Spec | None = None,
    ) -> project_module.BuildBundle: ...


class EngineFactory(typing.Protocol):
    """Create engines backed by test-owned synthetic bundles."""

    def __call__(
        self,
        execution_plan: execution_plan.ExecutionPlan,
        parameters: dict[str, object] | None = None,
        project_root: pathlib.Path | None = None,
        spec_definition: spec.Spec | None = None,
    ) -> engine_module.Engine: ...


def spec_for_plan(execution_plan: execution_plan.ExecutionPlan) -> spec_model.Spec:
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
    *,
    build_root: pathlib.Path,
) -> project_module.BuildBundle:
    """Wrap a plan in a test bundle for engine execution."""
    root = (project_root or REPOSITORY_ROOT).resolve()
    build_root.mkdir(parents=True)
    bundle_spec = spec_definition or spec_for_plan(execution_plan)
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
