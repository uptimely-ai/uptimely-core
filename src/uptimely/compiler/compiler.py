"""Compile spec into portable execution plans."""

from __future__ import annotations

import logging
import pathlib
import typing
from collections import abc

from uptimely import entrypoint, spec
from uptimely.spec import model as spec_model
from uptimely.spec import references as bindings

from . import callable_node as callable_node_module
from . import execution_graph, plan

logger = logging.getLogger(__name__)

ExecutionPlan = plan.ExecutionPlan


def _resolve_function(
    spec_definition: spec.Spec, node: callable_node_module.CallableNode
) -> spec_model.FunctionTemplate | None:
    """Return the function definition for an operation node."""
    return spec_definition.functions.get(node.function_id)


def _portable_value(value: object) -> object:
    """Convert Pydantic binding values recursively to JSON-compatible data."""
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    if isinstance(value, dict):
        return {name: _portable_value(item) for name, item in value.items()}
    if isinstance(value, list):
        return [_portable_value(item) for item in value]
    return value


def _resource_models(spec_definition: spec.Spec) -> dict[str, typing.Any]:
    """Export spec data required by the engine at runtime."""
    return {
        "dimensions": {
            identifier: dimension.model_dump(exclude_none=False)
            for identifier, dimension in spec_definition.dimensions.items()
        },
        "entities": {
            identifier: {"id": entity.id, "dimensions": entity.dimension_ids}
            for identifier, entity in spec_definition.entities.items()
        },
        "functions": spec_definition.functions.model_dump(exclude_none=False),
        "datasets": {
            dataset.id: {
                "features": {
                    identifier: feature.model_dump(exclude_none=True)
                    for identifier, feature in dataset.features.items()
                },
                "order": [key.model_dump() for key in dataset.order],
                "row_scope": dataset.row_scope.model_dump(),
            }
            for entity in spec_definition.entities.values()
            for dataset in entity.datasets
        },
    }


class Compiler:
    """Turn a Spec instance or JSON path into a portable execution plan."""

    def __init__(
        self,
        spec_definition: str | pathlib.Path | spec.Spec,
        features: abc.Collection[str] | None = None,
    ) -> None:
        """Initialize the compiler with spec or a JSON path."""
        self.spec_path: pathlib.Path | None = None
        self.spec: spec.Spec | None = None
        self.features = self._validate_features(features)
        if isinstance(spec_definition, spec.Spec):
            self.spec = spec_definition
        else:
            self.spec_path = pathlib.Path(spec_definition)

    def compile(self) -> plan.ExecutionPlan:
        """Build and serialize the dependency graph into a portable plan."""
        if self.spec is None:
            if self.spec_path is None:
                raise ValueError("No spec or spec path provided.")
            self.spec = spec.load_spec(self.spec_path)

        callable_graph = execution_graph.CallableGraph(self.spec)
        if self.features is not None:
            logger.debug("Compiling feature subset: %s", sorted(self.features))
            callable_graph = callable_graph.subset(self.features)
        execution_stages = callable_graph.topology()
        callables = [self._callable(callable_graph, node) for node in callable_graph.callables]
        signatures = self._read_signatures(callable_graph)
        callable_ids = {callable.id for callable in callables}
        stages = [
            [node.node_id for node in stage if node.node_id in callable_ids]
            for stage in execution_stages
        ]
        resources = _resource_models(self.spec)
        resources["signatures"] = {
            node_id: signature.returns for node_id, signature in signatures.items()
        }
        execution_plan = plan.Plan(
            plan_version=plan.PLAN_VERSION,
            required_backend="polars",
            resources=resources,
            callables=callables,
            stages=stages,
        )
        logger.info("Compiled plan: %d callables in %d stages", len(callables), len(stages))
        return plan.ExecutionPlan(execution_plan)

    def _callable(
        self, graph: execution_graph.CallableGraph, node: callable_node_module.CallableNode
    ) -> plan.Callable:
        """Convert one live graph node into a portable callable DTO."""
        function = _resolve_function(self.spec, node)
        if function is None or not function.entrypoint:
            raise ValueError(f"Missing entrypoint for function: {node.function_id}")
        arguments = bindings.resolve_binding_args(
            node.args,
            node.dataset_id,
            (
                next(
                    feature
                    for feature in node.output_features
                    if feature not in self.spec.entities[node.entity].dimension_ids
                )
                if node.operation == "collapse"
                else node.feature
                if node.operation == "vectorize"
                else None
            ),
        )
        return plan.Callable(
            id=node.node_id,
            operation=node.operation,
            entrypoint=function.entrypoint,
            entity_id=node.entity,
            dataset_id=node.dataset_id,
            output=node.feature or node.mapping_id,
            output_features=list(node.output_features),
            input_features=graph.mapping_for(node).input_features,
            arguments=_portable_value(arguments),
            dependency_ids=[dependency.node_id for dependency in graph.dependencies(node)],
            row_context=node.row_context,
        )

    @staticmethod
    def _validate_features(features: abc.Collection[str] | None) -> list[str] | None:
        """Return requested feature identifiers in their supplied order."""
        if features is None:
            return None
        if isinstance(features, str):
            raise ValueError("features must be a collection of feature identifiers")
        return list(dict.fromkeys(features))

    def _read_signatures(self, callable_graph: execution_graph.CallableGraph) -> dict[str, object]:
        """Read callable signatures for compiler diagnostics."""
        signatures: dict[str, object] = {}
        for node in callable_graph.callables:
            function = _resolve_function(self.spec, node)
            if function is None or not function.entrypoint:
                continue
            try:
                signature = entrypoint.read_signature(function.entrypoint, pathlib.Path.cwd())
            except (ImportError, AttributeError, ValueError, TypeError) as error:
                raise ValueError(
                    f"Could not read signature of function {function.id} "
                    f"from entrypoint {function.entrypoint}: {error}"
                ) from error
            self._validate_return_annotation(function, signature.returns)
            signatures[node.node_id] = signature
        return signatures

    @staticmethod
    def _validate_return_annotation(
        function: spec_model.FunctionTemplate, annotation: str | None
    ) -> None:
        """Require the Python return annotation to satisfy the function contract."""
        returns = function.returns
        if annotation is None:
            raise ValueError(
                f"Function {function.id} must annotate its return as "
                f"{'None' if returns == 'none' else 'DataFrame or LazyFrame'}"
            )
        members = {member.strip().rsplit(".", 1)[-1] for member in annotation.split(" | ")}
        if returns == "none":
            compatible = members == {"None"}
        else:
            compatible = bool(members) and members <= {"DataFrame", "LazyFrame"}
        if not compatible:
            expected = "None" if returns == "none" else "DataFrame or LazyFrame"
            raise ValueError(
                f"Function {function.id} declares returns={returns}, but its Python "
                f"return annotation is {annotation}; expected {expected}"
            )
