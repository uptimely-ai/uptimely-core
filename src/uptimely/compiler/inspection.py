"""Inspect implementation entrypoints and validate compile-time contracts."""

from __future__ import annotations

from uptimely import entrypoint, spec
from uptimely.spec import model as spec_model

from . import graph as invocation_graph


def read_entrypoints(
    spec_definition: spec.Spec,
    graph: invocation_graph.InvocationGraph,
) -> dict[str, entrypoint.Entrypoint]:
    """Parse each distinct implementation location once."""
    entrypoints: dict[str, entrypoint.Entrypoint] = {}
    for node in graph.invocations:
        function = spec_definition.functions[node.function_id]
        if function.entrypoint in entrypoints:
            continue
        try:
            entrypoints[function.entrypoint] = entrypoint.Entrypoint(function.entrypoint)
        except ValueError as error:
            raise ValueError(
                f"Invalid entrypoint for function {function.id} "
                f"used by mapping {node.mapping_id}: {error}"
            ) from error
    return entrypoints


def read_packages(
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


def read_signatures(
    spec_definition: spec.Spec,
    graph: invocation_graph.InvocationGraph,
    entrypoints: dict[str, entrypoint.Entrypoint],
) -> dict[str, entrypoint.Signature]:
    """Inspect enabled function declarations and validate their return contracts."""
    signatures: dict[str, entrypoint.Signature] = {}
    signatures_by_function: dict[str, entrypoint.Signature] = {}
    for node in graph.invocations:
        function = spec_definition.functions.get(node.function_id)
        if function is None or not function.validate_signature:
            continue

        signature = signatures_by_function.get(function.id)
        if signature is None:
            implementation = entrypoints[function.entrypoint]
            try:
                signature = implementation.function.signature
                validate_return_annotation(function, signature.returns)
            except (ImportError, AttributeError, ValueError, TypeError) as error:
                raise ValueError(
                    f"Could not read signature of function {function.id} "
                    f"used by mapping {node.mapping_id} from entrypoint "
                    f"{function.entrypoint}; available build package: "
                    f"{implementation.module.package}: {error}"
                ) from error
            signatures_by_function[function.id] = signature
        signatures[node.node_id] = signature
    return signatures


def validate_return_annotation(
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
