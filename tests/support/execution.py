"""Construct test bundles and engines from hand-authored plans."""

import copy
import pathlib
import typing

from uptimely import engine as engine_module
from uptimely import plan as execution_plan
from uptimely import project as project_module
from uptimely import spec
from uptimely.engine.dataframe import backend as backend_module
from uptimely.engine.dataframe import dataset as dataset_module
from uptimely.engine.dataframe import fragment as fragment_module
from uptimely.spec import model as spec_model


def dataset(
    dataframe: object | None,
    id_columns: typing.Sequence[str] = (),
    *,
    backend: backend_module.DataFrameBackend | None = None,
) -> dataset_module.Dataset:
    """Create an independent physical accumulator for runtime tests."""
    adapter = backend if backend is not None else backend_module.PolarsBackend()
    return dataset_module.Dataset(adapter, id_columns, dataframe)


def merge_fragment(
    main: dataset_module.Dataset,
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
        operator_id="read",
        dataset_id="dataset",
        id_columns=list(main.id_columns),
        column_types=dict(dimension_types or {}),
    )
    if fragment.invocation is not None:
        fragment = fragment_module.Fragment.stage(
            main.backend,
            fragment.invocation,
            lambda: fragment.dataframe,
            validate=True,
            comparison_frame=main.dataframe,
        )
    else:
        fragment.validate_invocation_result(
            main.backend,
            invocation,
            output_features=[],
        )
    if main.dataframe is not None:
        main.validate_accumulated_frame(
            description="Accumulated profile",
            column_types=invocation.column_types,
        )
        main.validate_fragment_merge(fragment)
    main.merge(
        fragment,
        fragment_id=fragment.invocation.operator_id if fragment.invocation is not None else None,
        join_cardinality="1:1",
        broadcast_cardinality="m:1",
    )
    return fragment


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
    dimensions = dict(resources.get("dimensions", {}))
    profiles = {
        profile_id: dict(profile) for profile_id, profile in resources.get("profiles", {}).items()
    }
    functions = dict(resources.get("functions", {}))

    for invocation in execution_plan.invocations:
        if invocation.dataset_id is None:
            continue
        profile = profiles.setdefault(invocation.dataset_id, {"grain": []})
        if not profile.get("grain") and invocation.id_columns:
            profile["grain"] = []
            for key in invocation.id_columns:
                dimension_id = key
                resolution_id = key
                dimensions.setdefault(
                    dimension_id,
                    {
                        "resolutions": {
                            resolution_id: {
                                "key": key,
                                "type": invocation.column_types.get(key, "string"),
                            }
                        }
                    },
                )
                profile["grain"].append({"dimension": dimension_id, "resolution": resolution_id})
        function = functions.setdefault(invocation.function_id, {})
        function.setdefault("kind", invocation.function_kind)
        function.setdefault(
            "returns",
            {"escape": "any", "write": "none"}.get(invocation.function_kind, "dataframe"),
        )
        function.setdefault("entrypoint", invocation.entrypoint)
        function.setdefault("args", {})
        profile.setdefault("name", invocation.dataset_id)
        features = profile.setdefault("features", {})
        for feature in invocation.output_features:
            features.setdefault(
                feature,
                {"type": invocation.column_types.get(feature)},
            )
        profile.setdefault("assembly", {}).setdefault(
            invocation.operator_id,
            {
                "compute": {"function": invocation.function_id},
                "interface": {
                    "inputs": [f"$features.{name}" for name in invocation.input_features],
                    "outputs": [f"$features.{name}" for name in invocation.output_features],
                },
            },
        )

    return spec_model.Spec.model_validate(
        {
            "dimensions": dimensions,
            "functions": functions,
            "profiles": profiles,
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
    root = (project_root or build_root.parent).resolve()
    build_root.mkdir(parents=True)
    bundle_spec = spec_definition or spec_for_plan(execution_plan)
    if spec_definition is None:
        execution_plan = copy.replace(
            execution_plan,
            invocations=[
                copy.replace(
                    invocation,
                    id_columns=(
                        invocation.id_columns
                        or bundle_spec.grain_keys_by_profile[invocation.dataset_id]
                    ),
                    column_types={
                        **{
                            key: feature.type
                            for key, feature in bundle_spec.profiles[
                                invocation.dataset_id
                            ].features.items()
                            if feature.type is not None
                        },
                        **bundle_spec.grain_key_types_by_profile[invocation.dataset_id],
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
        execution_plan=execution_plan,
    )
