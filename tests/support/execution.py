"""Construct test bundles and engines from hand-authored plans."""

import dataclasses
import pathlib
import typing

from uptimely import engine as engine_module
from uptimely import execution_plan, spec
from uptimely import project as project_module
from uptimely.engine.dataframe import backend as backend_module
from uptimely.engine.dataframe import fragment as fragment_module
from uptimely.engine.dataframe import main_frame as main_frame_module
from uptimely.engine.dataframe import validation as dataframe_validation
from uptimely.engine.runtime import execution as execution_module
from uptimely.engine.runtime import state as state_module
from uptimely.spec import model as spec_model

REPOSITORY_ROOT = pathlib.Path(__file__).parents[2]


def main_frame(
    dataframe: object | None,
    id_columns: typing.Sequence[str] = (),
    *,
    backend: backend_module.DataFrameBackend | None = None,
) -> main_frame_module.MainFrame:
    """Create an independent physical accumulator for runtime tests."""
    adapter = backend if backend is not None else backend_module.PolarsBackend()
    return main_frame_module.MainFrame(adapter, id_columns, dataframe)


def merge_fragment(
    main: main_frame_module.MainFrame,
    fragment: fragment_module.Fragment,
    *,
    dimension_types: typing.Mapping[str, str] | None = None,
) -> fragment_module.Fragment:
    """Exercise runtime validation and projection around a physical accumulator."""
    invocation = fragment.invocation or execution_plan.Invocation(
        id="standalone",
        function_kind="read",
        entrypoint="test:read",
        function_id="read",
        mapping_id="read",
        entity_id="entity",
        dataset_id="dataset",
        id_columns=list(main.id_columns),
        column_types=dict(dimension_types or {}),
    )
    state = state_module.RuntimeState(main_frames={invocation.dataset_id: main})
    executor = execution_module.InvocationExecutor(main.backend, {}, {}, state, validate=True)
    if fragment.invocation is not None:
        fragment = fragment_module.Fragment.stage(
            main.backend,
            fragment.invocation,
            lambda: fragment.dataframe,
            validate=True,
            comparison_frame=main.dataframe,
        )
    else:
        dataframe_validation.FragmentValidator(
            main.backend,
            fragment.dataframe,
            list(fragment.dimensions),
            "Fragment",
            invocation=invocation,
            output_features=[],
        ).validate()
    return executor._merge_fragment(invocation, fragment)


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
        dataset = entity.setdefault("datasets", {}).setdefault(invocation.dataset_id, {})
        dataset.setdefault("actions", {}).setdefault(
            invocation.mapping_id,
            {"id": invocation.mapping_id, "binding": {"function": invocation.function_id}},
        )

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
    if spec_definition is None:
        execution_plan = dataclasses.replace(
            execution_plan,
            invocations=[
                dataclasses.replace(
                    invocation,
                    id_columns=(
                        invocation.id_columns
                        or bundle_spec.dimension_ids_by_dataset[invocation.dataset_id]
                    ),
                    column_types={
                        **{
                            key: definition.type
                            for key, definition in {
                                **bundle_spec.datasets[invocation.dataset_id].features,
                                **{
                                    key: bundle_spec.dimensions[key]
                                    for key in bundle_spec.dimension_ids_by_dataset[
                                        invocation.dataset_id
                                    ]
                                },
                            }.items()
                            if definition.type is not None
                        },
                        **invocation.column_types,
                    },
                    argument_types={
                        **{
                            key: argument.type
                            for key, argument in bundle_spec.functions[
                                invocation.function_id
                            ].args.items()
                        },
                        **invocation.argument_types,
                    },
                )
                for invocation in execution_plan.invocations
            ],
        )
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
            ),
        ),
        spec_path=build_root / "spec.json",
        spec_definition=bundle_spec,
        execution_plan_path=build_root / "execution_plan.json",
        explorer_path=build_root / "explorer",
        execution_plan=execution_plan,
    )
