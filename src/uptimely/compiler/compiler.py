"""Compile a loaded Spec into a portable execution plan."""

from __future__ import annotations

import logging
from collections import abc

from uptimely import execution_plan, spec
from uptimely.spec import validation

from . import validation as compiler_validation

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
        selected_features = self._normalize_features(features)
        validation.validate_spec(spec_definition)

        context = compiler_validation.CompilationContext(spec_definition, selected_features)
        compiler_validation.validate_compilation(context)

        invocation_ids = {invocation.id for invocation in context.invocations}
        stages = [
            [node.node_id for node in stage if node.node_id in invocation_ids]
            for stage in context.execution_stages
        ]
        resources = {
            "signatures": {
                node_id: signature.returns for node_id, signature in context.signatures.items()
            },
            "entrypoint_packages": {
                location: {
                    "distribution": package.distribution,
                    "version": package.version,
                }
                for location, package in context.packages.items()
            },
        }
        compiled_plan = execution_plan.ExecutionPlan(
            plan_version=execution_plan.PLAN_VERSION,
            required_backend="polars",
            resources=resources,
            invocations=context.invocations,
            stages=stages,
        )
        logger.debug(
            "Compiled plan: %d invocations in %d stages",
            len(context.invocations),
            len(stages),
        )
        return compiled_plan

    @staticmethod
    def _normalize_features(features: abc.Collection[str] | None) -> list[str] | None:
        """Deduplicate requested feature identifiers while preserving their order."""
        if features is None:
            return None
        if isinstance(features, str):
            raise ValueError("features must be a collection of feature identifiers")
        return list(dict.fromkeys(features))
