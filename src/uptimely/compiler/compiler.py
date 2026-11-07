"""Compile a loaded Spec into a portable execution plan."""

from __future__ import annotations

import functools
import logging
import typing
from collections import abc

from uptimely import entrypoint, execution_plan, spec
from uptimely.spec import validation as spec_validation
from uptimely.spec.validation import errors

from . import graph as invocation_graph
from . import plan_emission, validation

logger = logging.getLogger(__name__)


class Compiler:
    """Turn a Spec into a portable execution plan."""

    def __init__(self) -> None:
        """Initialize a compiler with no active compilation."""
        self._spec_definition: spec.Spec | None = None
        self.features: abc.Collection[str] | None = None

    @property
    def spec_definition(self) -> spec.Spec:
        """Return the specification supplied to the current compilation."""
        if self._spec_definition is None:
            raise RuntimeError("Call compile() before accessing compiler build properties")
        return self._spec_definition

    @functools.cached_property
    def graph(self) -> invocation_graph.InvocationGraph:
        """Build the validated invocation graph for the selected features."""
        graph = invocation_graph.InvocationGraph(self.spec_definition)
        if self.features is not None:
            logger.debug(
                "\nCompiler feature selection:\n  Selected features: %s", sorted(self.features)
            )
            return graph.subset(list(dict.fromkeys(self.features)))
        logger.debug("\nCompiler feature selection:\n  - using all features")
        return graph

    @functools.cached_property
    def execution_stages(self) -> list[list[invocation_graph.InvocationNode]]:
        """Return invocation dependency levels, rejecting unschedulable graphs."""
        return self.graph.topology()

    @functools.cached_property
    def invocations(self) -> list[execution_plan.Invocation]:
        """Emit portable invocations after validating schedulability."""
        _ = self.execution_stages
        nodes = self.graph.invocations
        logger.debug("  Invocation checks for %d invocations:", len(nodes))
        logger.debug("    - checking functions declare entrypoints")
        logger.debug("    - checking structural argument references resolve")
        logger.debug("    - checking emitted invocation contracts")
        return [
            plan_emission.emit_invocation(self.spec_definition, self.graph, node) for node in nodes
        ]

    @functools.cached_property
    def entrypoints(self) -> dict[str, entrypoint.Entrypoint]:
        """Parse the selected invocations' implementation locations."""
        entrypoints: dict[str, entrypoint.Entrypoint] = {}
        locations = dict.fromkeys(invocation.entrypoint for invocation in self.invocations)
        logger.debug("  Entrypoints:")
        logger.debug("    - checking syntax for %d unique entrypoints", len(locations))
        for location in locations:
            try:
                entrypoints[location] = entrypoint.Entrypoint(location)
            except ValueError as error:
                raise ValueError(f"Invalid entrypoint {location!r}: {error}") from error
        return entrypoints

    @functools.cached_property
    def packages(self) -> dict[str, entrypoint.PackageProvenance]:
        """Read package provenance for selected implementations."""
        packages: dict[str, entrypoint.PackageProvenance] = {}
        implementations = self.entrypoints
        logger.debug("  Package provenance:")
        logger.debug(
            "    - checking package ownership for %d unique entrypoints", len(implementations)
        )
        for location, implementation in implementations.items():
            try:
                packages[location] = implementation.module.package
            except (ImportError, ValueError) as error:
                raise ValueError(
                    f"Could not read package provenance for entrypoint {location}: {error}"
                ) from error
        return packages

    @functools.cached_property
    def function_signatures(self) -> dict[str, entrypoint.Signature]:
        """Inspect and validate each enabled function contract once."""
        _ = self.packages
        signatures: dict[str, entrypoint.Signature] = {}
        nodes = self.graph.invocations
        selected_functions = {
            node.function_id: self.spec_definition.functions.get(node.function_id) for node in nodes
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
        for node in nodes:
            function = self.spec_definition.functions.get(node.function_id)
            if function is None:
                continue
            if not function.validate_signature:
                continue
            if function.id in signatures:
                continue
            implementation = self.entrypoints[function.entrypoint]
            try:
                signature = implementation.function.signature
                validation.validation_callable_signature(
                    validation.CallableValidationContext(function, signature)
                )
            except errors.SpecError:
                raise
            except (ImportError, AttributeError, ValueError, TypeError, NameError) as error:
                raise ValueError(
                    f"Could not read signature of function {function.id} "
                    f"used by operator {node.operator_id} from entrypoint "
                    f"{function.entrypoint}; available build package: "
                    f"{self.packages[function.entrypoint]}: {error}"
                ) from error
            signatures[function.id] = signature
        return signatures

    @functools.cached_property
    def signatures(self) -> dict[str, entrypoint.Signature]:
        """Map selected invocations to their validated function signatures."""
        function_signatures = self.function_signatures
        return {
            node.node_id: function_signatures[node.function_id]
            for node in self.graph.invocations
            if node.function_id in function_signatures
        }

    @functools.cached_property
    def stages(self) -> list[list[str]]:
        """Return execution stages containing emitted invocation IDs only."""
        invocation_ids = {invocation.id for invocation in self.invocations}
        return [
            [node.node_id for node in stage if node.node_id in invocation_ids]
            for stage in self.execution_stages
        ]

    @functools.cached_property
    def signature_resources(self) -> dict[str, str | None]:
        """Return invocation return annotations for the portable plan."""
        return {node_id: signature.returns for node_id, signature in self.signatures.items()}

    @functools.cached_property
    def entrypoint_packages(self) -> dict[str, dict[str, str | None]]:
        """Return serialized package provenance for the portable plan."""
        return {location: package.to_dict() for location, package in self.packages.items()}

    @functools.cached_property
    def resources(self) -> dict[str, typing.Any]:
        """Combine portable signature and package metadata."""
        return {
            "signatures": self.signature_resources,
            "entrypoint_packages": self.entrypoint_packages,
        }

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
        for name in (
            "graph",
            "execution_stages",
            "invocations",
            "entrypoints",
            "packages",
            "function_signatures",
            "signatures",
            "stages",
            "signature_resources",
            "entrypoint_packages",
            "resources",
        ):
            self.__dict__.pop(name, None)
        self._spec_definition = None
        self.features = features
        spec_validation.validate_spec(spec_definition)
        logger.debug("\nCompiler validation:")
        validation.validation_feature_selection(self.features)
        self._spec_definition = spec_definition
        resources = self.resources
        logger.debug("  Execution plan:")
        logger.debug("    - checking emitted invocation IDs, dependencies, and stage ordering")
        return execution_plan.ExecutionPlan(
            plan_version=execution_plan.PLAN_VERSION,
            required_backend="polars",
            resources=resources,
            invocations=self.invocations,
            stages=self.stages,
        )
