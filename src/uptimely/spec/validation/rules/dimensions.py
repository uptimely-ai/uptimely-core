"""Atomic dimension parent-reference and ancestry checks."""

from __future__ import annotations

import collections.abc
import logging

from uptimely.spec import model as spec_model
from uptimely.spec.validation import errors

logger = logging.getLogger(__name__)


def iter_parent_cycles(
    spec: spec_model.Spec,
) -> collections.abc.Iterator[tuple[tuple[str, str], tuple[tuple[str, str], ...]]]:
    """Yield each resolution and any cycle reached through its same-dimension parents."""
    for dimension_id, dimension in spec.dimensions.items():
        for resolution_id in dimension.resolutions:
            chain: list[str] = []
            current: str | None = resolution_id
            while current is not None and current not in chain:
                chain.append(current)
                resolution = dimension.resolutions.get(current)
                current = resolution.parent if resolution is not None else None
            cycle_ids = chain[chain.index(current) :] + [current] if current is not None else []
            yield (
                (dimension_id, resolution_id),
                tuple((dimension_id, item) for item in cycle_ids),
            )


def validate_parent(spec: spec_model.Spec) -> None:
    """Require each resolution parent to be declared within the same dimension."""
    logger.debug("    - checking dimension-resolution parent references")
    for dimension_id, dimension in spec.dimensions.items():
        for resolution_id, resolution in dimension.resolutions.items():
            if resolution.parent is not None and resolution.parent not in dimension.resolutions:
                raise ValueError(
                    f"Dimension {dimension_id} resolution {resolution_id} references "
                    f"unknown parent resolution: {resolution.parent}"
                )


def validate_parent_cycle(spec: spec_model.Spec) -> None:
    """Reject a cycle in resolution ancestry after parent references are validated."""
    logger.debug("    - checking resolution ancestry is acyclic")
    for (dimension_id, resolution_id), cycle in iter_parent_cycles(spec):
        if cycle:
            raise errors.SpecError(
                "Dimension resolution parent cycle: "
                + " -> ".join(f"{dimension}.{resolution}" for dimension, resolution in cycle),
                code="dimension_resolution_parent_cycle",
                path=("dimensions", dimension_id, "resolutions", resolution_id, "parent"),
            )
