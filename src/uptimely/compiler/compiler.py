"""Compile spec into portable execution plans."""

from __future__ import annotations

import logging
import pathlib
from collections import abc

from uptimely import entrypoint, execution_plan, spec
from uptimely.spec import model as spec_model
from uptimely.spec import operations
from uptimely.spec import references as bindings

from . import callable_node as callable_node_module
from . import execution_graph

logger = logging.getLogger(__name__)


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

    def compile(self) -> execution_plan.ExecutionPlan:
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
        entrypoints = self._read_entrypoints(callables)
        packages = self._read_packages(entrypoints)
        signatures = self._read_signatures(callable_graph, entrypoints)
        callable_ids = {callable.id for callable in callables}
        stages = [
            [node.node_id for node in stage if node.node_id in callable_ids]
            for stage in execution_stages
        ]
        resources = {
            "signatures": {node_id: signature.returns for node_id, signature in signatures.items()},
            "entrypoint_packages": {
                location: {
                    "distribution": package.distribution,
                    "version": package.version,
                }
                for location, package in packages.items()
            },
        }
        compiled_plan = execution_plan.ExecutionPlan(
            plan_version=execution_plan.PLAN_VERSION,
            required_backend="polars",
            resources=resources,
            callables=callables,
            stages=stages,
        )
        logger.debug("Compiled plan: %d callables in %d stages", len(callables), len(stages))
        return compiled_plan

    def _callable(
        self, graph: execution_graph.CallableGraph, node: callable_node_module.CallableNode
    ) -> execution_plan.Callable:
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
                if node.operation == operations.COLLAPSE
                else node.feature
                if node.operation == operations.VECTORIZE
                else None
            ),
        )
        return execution_plan.Callable(
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

    @staticmethod
    def _read_entrypoints(
        callables: list[execution_plan.Callable],
    ) -> dict[str, entrypoint.Entrypoint]:
        """Parse each distinct implementation location once."""
        entrypoints: dict[str, entrypoint.Entrypoint] = {}
        for callable in callables:
            if callable.entrypoint in entrypoints:
                continue
            try:
                entrypoints[callable.entrypoint] = entrypoint.Entrypoint(callable.entrypoint)
            except ValueError as error:
                raise ValueError(
                    f"Invalid entrypoint for function {callable.function_id}: {error}"
                ) from error
        return entrypoints

    @staticmethod
    def _read_packages(
        entrypoints: dict[str, entrypoint.Entrypoint],
    ) -> dict[str, entrypoint.PackageProvenance]:
        """Read package provenance independently of signature validation."""
        packages: dict[str, entrypoint.PackageProvenance] = {}
        for location, implementation in entrypoints.items():
            try:
                packages[location] = implementation.module.package
            except (ImportError, ValueError) as error:
                raise ValueError(
                    f"Could not read package provenance for entrypoint {location}: {error}"
                ) from error
        return packages

    def _read_signatures(
        self,
        callable_graph: execution_graph.CallableGraph,
        entrypoints: dict[str, entrypoint.Entrypoint],
    ) -> dict[str, entrypoint.Signature]:
        """Inspect enabled signatures and validate their return contracts."""
        signatures: dict[str, entrypoint.Signature] = {}
        for node in callable_graph.callables:
            function = _resolve_function(self.spec, node)
            if function is None or not function.validate_signature:
                continue
            implementation = entrypoints[function.entrypoint]
            try:
                signature = implementation.function.signature
                self._validate_return_annotation(function, signature.returns)
            except (ImportError, AttributeError, ValueError, TypeError) as error:
                raise ValueError(
                    f"Could not read signature of function {function.id} "
                    f"from entrypoint {function.entrypoint}; "
                    f"available build package: {implementation.module.package}: {error}"
                ) from error
            signatures[node.node_id] = signature
        return signatures

    @staticmethod
    def _validate_return_annotation(
        function: spec_model.FunctionTemplate, annotation: str | None
    ) -> None:
        """Require the Python return annotation to satisfy the function contract."""
        returns = function.returns
        if returns == "any":
            return
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
