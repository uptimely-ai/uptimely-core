"""Atomic dimension parent-reference and ancestry checks."""

from __future__ import annotations

import collections.abc

from uptimely.spec import model as spec_model
from uptimely.spec.validation import errors


def iter_parent_cycles(
    spec: spec_model.Spec,
) -> collections.abc.Iterator[tuple[str, tuple[str, ...]]]:
    """Yield each dimension and any cycle reached by walking its ancestry."""
    for dimension_id in spec.dimensions:
        chain: list[str] = []
        current: str | None = dimension_id
        while current is not None and current not in chain:
            chain.append(current)
            declaration = spec.dimensions.get(current)
            current = declaration.parent if declaration is not None else None
        cycle = tuple(chain[chain.index(current) :] + [current]) if current is not None else ()
        yield dimension_id, cycle


def validate_parent(spec: spec_model.Spec) -> None:
    """Require a dimension's parent to be declared."""
    for dimension_id, dimension in spec.dimensions.items():
        if dimension.parent is not None and dimension.parent not in spec.dimensions:
            raise ValueError(
                f"Dimension {dimension_id} references unknown parent: {dimension.parent}"
            )


def validate_parent_cycle(spec: spec_model.Spec) -> None:
    """Reject a cycle in dimension ancestry after parent references are validated."""
    for dimension_id, cycle in iter_parent_cycles(spec):
        if cycle:
            raise errors.SpecError(
                "Dimension parent cycle: " + " -> ".join(cycle),
                code="dimension_parent_cycle",
                path=("dimensions", dimension_id, "parent"),
            )
