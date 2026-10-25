"""Compile a loaded Spec into a portable execution plan."""

from __future__ import annotations

import logging
from collections import abc

from uptimely import execution_plan, spec
from uptimely.spec import validation

from . import graph as invocation_graph
from . import inspection, plan_emission

logger = logging.getLogger(__name__)


class Compiler:
    """Turn a Spec into a portable execution plan."""

    def compile(
        self,
        spec_definition: spec.Spec,
        features: abc.Collection[str] | None = None,
    ) -> execution_plan.ExecutionPlan:
        """Validate and compile a Spec, optionally selecting output features.

        Args:
            spec_definition: The Spec document to compile.
            features: Optional collection of output feature identifiers.

        Returns:
            A portable execution plan for the selected invocation graph.

        Raises:
            ValueError: The Spec, feature selection, or implementation contract is invalid.
        """
        selected_features = self._validate_features(features)
        validation.validate_spec(spec_definition)

        graph = invocation_graph.InvocationGraph(spec_definition)
        if selected_features is not None:
            logger.debug("Compiling feature subset: %s", sorted(selected_features))
            graph = graph.subset(selected_features)

        execution_stages = graph.topology()
        invocations = plan_emission.emit_invocations(spec_definition, graph)
        entrypoints = inspection.read_entrypoints(spec_definition, graph)
        packages = inspection.read_packages(entrypoints)
        signatures = inspection.read_signatures(spec_definition, graph, entrypoints)

        invocation_ids = {invocation.id for invocation in invocations}
        stages = [
            [node.node_id for node in stage if node.node_id in invocation_ids]
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
            invocations=invocations,
            stages=stages,
        )
        logger.debug("Compiled plan: %d invocations in %d stages", len(invocations), len(stages))
        return compiled_plan

    @staticmethod
    def _validate_features(features: abc.Collection[str] | None) -> list[str] | None:
        """Return requested feature identifiers in their supplied order."""
        if features is None:
            return None
        if isinstance(features, str):
            raise ValueError("features must be a collection of feature identifiers")
        return list(dict.fromkeys(features))
