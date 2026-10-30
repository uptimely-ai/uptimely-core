"""Run compiler-build validators in explicit prerequisite order."""

from __future__ import annotations

import collections.abc
import dataclasses
import graphlib
import logging

from uptimely import entrypoint, execution_plan, spec

from . import graph as invocation_graph
from . import inspection, plan_emission

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class CompilationContext:
    """Mutable results shared by compiler-build validators."""

    spec_definition: spec.Spec
    selected_features: list[str] | None
    graph: invocation_graph.InvocationGraph | None = None
    execution_stages: list[list[invocation_graph.InvocationNode]] = dataclasses.field(
        default_factory=list
    )
    invocations: list[execution_plan.Invocation] = dataclasses.field(default_factory=list)
    entrypoints: dict[str, entrypoint.Entrypoint] = dataclasses.field(default_factory=dict)
    packages: dict[str, entrypoint.PackageProvenance] = dataclasses.field(default_factory=dict)
    signatures: dict[str, entrypoint.Signature] = dataclasses.field(default_factory=dict)


type Validator = collections.abc.Callable[[CompilationContext], None]


def validate_invocation_graph(context: CompilationContext) -> None:
    """Construct the invocation graph from a semantically valid spec."""
    context.graph = invocation_graph.InvocationGraph(context.spec_definition)


def validate_feature_selection(context: CompilationContext) -> None:
    """Resolve the requested feature selection against the invocation graph."""
    graph = _require_graph(context)
    if context.selected_features is not None:
        logger.debug("Compiling feature subset: %s", sorted(context.selected_features))
        context.graph = graph.subset(context.selected_features)


def validate_schedulability(context: CompilationContext) -> None:
    """Resolve invocation dependency levels, rejecting unschedulable graphs."""
    context.execution_stages = _require_graph(context).topology()


def validate_invocations(context: CompilationContext) -> None:
    """Emit invocations and validate their compile-time bindings."""
    context.invocations = plan_emission.emit_invocations(
        context.spec_definition, _require_graph(context)
    )


def validate_entrypoints(context: CompilationContext) -> None:
    """Parse entrypoints referenced by the selected invocation graph."""
    context.entrypoints = inspection.read_entrypoints(
        context.spec_definition, _require_graph(context)
    )


def validate_packages(context: CompilationContext) -> None:
    """Read package provenance for selected entrypoints."""
    context.packages = inspection.read_packages(context.entrypoints)


def validate_signatures(context: CompilationContext) -> None:
    """Check selected implementations against their declared callable contracts."""
    context.signatures = inspection.read_signatures(
        context.spec_definition, _require_graph(context), context.entrypoints
    )


COMPILATION_VALIDATION_DEPENDENCIES: dict[Validator, tuple[Validator, ...]] = {
    validate_invocation_graph: (),
    validate_feature_selection: (validate_invocation_graph,),
    validate_schedulability: (validate_feature_selection,),
    validate_invocations: (validate_feature_selection,),
    validate_entrypoints: (validate_feature_selection,),
    validate_packages: (validate_entrypoints,),
    validate_signatures: (validate_entrypoints,),
}


def validate_compilation(context: CompilationContext) -> None:
    """Run compiler-specific checks after the shared spec validation succeeds.

    Args:
        context: The state shared by compiler-build validators.

    Raises:
        ValueError: A compilation invariant is violated.
        graphlib.CycleError: Validator dependencies contain a configuration cycle.
    """
    ordered = tuple(graphlib.TopologicalSorter(COMPILATION_VALIDATION_DEPENDENCIES).static_order())
    for validate in ordered:
        validate(context)


def _require_graph(context: CompilationContext) -> invocation_graph.InvocationGraph:
    """Return the graph established by its prerequisite validator."""
    if context.graph is None:
        raise RuntimeError("Invocation graph validation must run before dependent checks")
    return context.graph
