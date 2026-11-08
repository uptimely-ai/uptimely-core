"""Compile a loaded Spec into a portable execution plan."""

from __future__ import annotations

import logging
import typing
from collections import abc

from uptimely import entrypoint, spec
from uptimely import plan as plan_module
from uptimely.spec import validation as spec_validation
from uptimely.spec.validation import errors

from . import graph as invocation_graph
from . import plan_emission, validation

logger = logging.getLogger(__name__)


class Compiler:
    """Turn Specs into portable execution plans without retaining build state."""

    def compile(
        self,
        spec_definition: spec.Spec,
        features: abc.Collection[str] | None = None,
    ) -> plan_module.ExecutionPlan:
        """Validate and compile a Spec using fresh state for this call.

        Args:
            spec_definition: The Spec document to compile.
            features: Optional collection of output feature identifiers.

        Returns:
            A portable execution plan for the selected invocation graph.

        Raises:
            ValueError: The Spec, feature selection, or implementation contract is invalid.
        """
        spec_validation.validate_spec(spec_definition)
        logger.debug("\nCompiler validation:")
        validation.validation_feature_selection(features)

        graph = invocation_graph.InvocationGraph(spec_definition)
        if features is not None:
            logger.debug("\nCompiler feature selection:\n  Selected features: %s", sorted(features))
            graph = graph.subset(list(dict.fromkeys(features)))
        else:
            logger.debug("\nCompiler feature selection:\n  - using all features")

        execution_stages = graph.topology()
        nodes = graph.invocations
        logger.debug("  Invocation checks for %d invocations:", len(nodes))
        logger.debug("    - checking functions declare entrypoints")
        logger.debug("    - checking structural argument references resolve")
        logger.debug("    - checking emitted invocation contracts")
        invocations = [
            plan_emission.emit_invocation(spec_definition, graph, node) for node in nodes
        ]

        locations = dict.fromkeys(invocation.entrypoint for invocation in invocations)
        logger.debug("  Entrypoints:")
        logger.debug("    - checking syntax for %d unique entrypoints", len(locations))
        entrypoints: dict[str, entrypoint.Entrypoint] = {}
        for location in locations:
            try:
                entrypoints[location] = entrypoint.Entrypoint(location)
            except ValueError as error:
                raise ValueError(f"Invalid entrypoint {location!r}: {error}") from error

        logger.debug("  Package provenance:")
        logger.debug("    - checking package ownership for %d unique entrypoints", len(locations))
        packages: dict[str, entrypoint.PackageProvenance] = {}
        for location, implementation in entrypoints.items():
            try:
                packages[location] = implementation.module.read_package()
            except (ImportError, ValueError) as error:
                raise ValueError(
                    f"Could not read package provenance for entrypoint {location}: {error}"
                ) from error

        selected_functions = {
            invocation.function_id: spec_definition.functions.get(invocation.function_id)
            for invocation in invocations
        }
        enabled_count = sum(
            function is not None and function.validate_signature
            for function in selected_functions.values()
        )
        disabled_count = sum(
            function is not None and not function.validate_signature
            for function in selected_functions.values()
        )
        logger.debug(
            "  Signature checks for %d functions:\n"
            "    - checking callable signatures\n"
            "    - checking implementations accept declared arguments\n"
            "    - checking declared arguments can be passed as keywords\n"
            "    - checking declared implementation argument annotations\n"
            "    - checking required implementation parameters are declared\n"
            "    - checking declared implementation return annotations",
            enabled_count,
        )
        if disabled_count:
            logger.debug("    - skipping %d functions (validate_signature=false)", disabled_count)

        signatures: dict[str, entrypoint.Signature] = {}
        for invocation in invocations:
            function = spec_definition.functions.get(invocation.function_id)
            if function is None or not function.validate_signature or function.id in signatures:
                continue
            implementation = entrypoints[function.entrypoint]
            try:
                signature = implementation.function.read_signature()
                validation.validation_callable_signature(
                    validation.CallableValidationContext(function, signature)
                )
            except errors.SpecError:
                raise
            except (ImportError, AttributeError, ValueError, TypeError, NameError) as error:
                raise ValueError(
                    f"Could not read signature of function {function.id} "
                    f"used by operator {invocation.operator_id} from entrypoint "
                    f"{function.entrypoint}; available build package: "
                    f"{packages[function.entrypoint]}: {error}"
                ) from error
            signatures[function.id] = signature

        resources: dict[str, typing.Any] = {
            "signatures": {
                invocation.id: signatures[invocation.function_id].returns
                for invocation in invocations
                if invocation.function_id in signatures
            },
            "entrypoint_packages": {
                location: package.to_dict() for location, package in packages.items()
            },
        }
        invocation_ids = {invocation.id for invocation in invocations}
        stages = [
            [node.node_id for node in stage if node.node_id in invocation_ids]
            for stage in execution_stages
        ]

        logger.debug("  Execution plan:")
        logger.debug("    - checking emitted invocation IDs, dependencies, and stage ordering")
        return plan_module.ExecutionPlan(
            plan_version=plan_module.PLAN_VERSION,
            required_backend="polars",
            resources=resources,
            invocations=invocations,
            stages=stages,
        )
