"""Compile analytics into portable execution plans."""

from __future__ import annotations

import logging
import pathlib
import typing
from collections import abc

from uptimely import analytics
from uptimely import plan as uptimely_plan
from uptimely.analytics.json import bindings, json_model

from . import entrypoint, execution_graph
from . import node as node_module

logger = logging.getLogger(__name__)

ExecutionPlan = uptimely_plan.ExecutionPlan


def _resolve_function(analytics_definition: analytics.Analytics, node: node_module.CallableNode):
    """Return the function definition for an operation node."""
    function = analytics_definition.function_catalog.get(node.function_id)
    if function is not None:
        return function
    return next(
        (
            function
            for function in analytics_definition.resolved_functions
            if function.id == node.function_id
        ),
        None,
    )


def _portable_value(value: object) -> object:
    """Convert Pydantic binding values recursively to JSON-compatible data."""
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    if isinstance(value, dict):
        return {name: _portable_value(item) for name, item in value.items()}
    if isinstance(value, list):
        return [_portable_value(item) for item in value]
    return value


def _resource_models(analytics_definition: analytics.Analytics) -> dict[str, typing.Any]:
    """Export analytics data required by the engine at runtime."""
    return {
        "analytics_version": analytics_definition.version,
        "dimensions": {
            identifier: dimension.model_dump(exclude_none=False)
            for identifier, dimension in analytics_definition.dimensions.items()
        },
        "entities": {
            identifier: {"id": entity.id, "dimensions": entity.dimension_ids}
            for identifier, entity in analytics_definition.entities.items()
        },
        "functions": analytics_definition.function_catalog.model_dump(exclude_none=False),
        "datasets": {
            dataset.id: {
                "features": {
                    identifier: feature.model_dump(exclude_none=True)
                    for identifier, feature in dataset.features.items()
                },
                "order": [key.model_dump() for key in dataset.order],
                "row_scope": dataset.row_scope.model_dump(),
            }
            for entity in analytics_definition.entities.values()
            for dataset in entity.datasets
        },
    }


class Compiler:
    """Turn an Analytics instance or JSON path into a portable execution plan."""

    def __init__(
        self,
        analytics_definition: str | pathlib.Path | analytics.Analytics,
        features: abc.Collection[str] | None = None,
    ) -> None:
        """Initialize the compiler with analytics or a JSON path."""
        self.analytics_path: pathlib.Path | None = None
        self.analytics: analytics.Analytics | None = None
        self.features = self._validate_features(features)
        if isinstance(analytics_definition, analytics.Analytics):
            self.analytics = analytics_definition
            self.analytics_path = (
                pathlib.Path(analytics_definition.path) if analytics_definition.path else None
            )
        else:
            self.analytics_path = pathlib.Path(analytics_definition)

    def compile(self) -> uptimely_plan.ExecutionPlan:
        """Build and serialize the dependency graph into a portable plan."""
        if self.analytics is None:
            if self.analytics_path is None:
                raise ValueError("No analytics or analytics path provided.")
            self.analytics = analytics.Analytics(json=self.analytics_path)

        callable_graph = execution_graph.CallableGraph(self.analytics)
        if self.features is not None:
            logger.debug("Compiling feature subset: %s", sorted(self.features))
            callable_graph = callable_graph.subset(self.features)
        execution_stages = callable_graph.topology()
        operations = [self._operation(callable_graph, node) for node in callable_graph.callables]
        signatures = self._read_signatures(callable_graph)
        operation_ids = {operation.id for operation in operations}
        stages = [
            [node.node_id for node in stage if node.node_id in operation_ids]
            for stage in execution_stages
        ]
        resources = _resource_models(self.analytics)
        resources["signatures"] = {
            node_id: signature.returns for node_id, signature in signatures.items()
        }
        plan = uptimely_plan.Plan(
            plan_version="1.0.0",
            analytics_version=self.analytics.version,
            required_backend="polars",
            resources=resources,
            operations=operations,
            stages=stages,
        )
        logger.info("Compiled plan: %d operations in %d stages", len(operations), len(stages))
        return uptimely_plan.ExecutionPlan(plan)

    def _operation(
        self, graph: execution_graph.CallableGraph, node: node_module.CallableNode
    ) -> uptimely_plan.Operation:
        """Convert one live graph node into a portable operation DTO."""
        function = _resolve_function(self.analytics, node)
        if function is None or not function.entrypoint:
            raise ValueError(f"Missing entrypoint for function: {node.function_id}")
        arguments = bindings.resolve_binding_args(
            node.args,
            node.dataset_id,
            (
                next(
                    feature
                    for feature in node.output_features
                    if feature not in self.analytics.entities[node.entity].dimension_ids
                )
                if node.operation_type == "collapse"
                else node.feature
                if node.operation_type == "vectorize"
                else None
            ),
        )
        return uptimely_plan.Operation(
            id=node.node_id,
            kind=node.operation_type,
            entrypoint=function.entrypoint,
            entity_id=node.entity,
            dataset_id=node.dataset_id,
            output=node.feature or node.operation_id,
            output_features=list(node.output_features),
            input_features=next(
                dataset.mappings[node.operation_id].input_features
                for dataset in self.analytics.entities[node.entity].datasets
                if dataset.id == node.dataset_id
            ),
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
            function = _resolve_function(self.analytics, node)
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
        function: json_model.FunctionTemplate, annotation: str | None
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
