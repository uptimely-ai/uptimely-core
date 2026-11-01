"""Validate engine configuration against a portable execution plan."""

from __future__ import annotations

import collections.abc
import graphlib

from uptimely import execution_plan
from uptimely.engine.dataframe import backend as backend_module

type Validator = collections.abc.Callable[
    [execution_plan.ExecutionPlan, backend_module.DataFrameBackend], None
]


def validate_plan_backend(
    plan: execution_plan.ExecutionPlan,
    backend: backend_module.DataFrameBackend,
) -> None:
    """Require the engine backend to match the saved plan."""
    if plan.required_backend != backend.name:
        raise ValueError(
            f"Unsupported plan backend: {plan.required_backend}. Expected {backend.name}."
        )


ENGINE_VALIDATION_DEPENDENCIES: dict[Validator, tuple[Validator, ...]] = {
    validate_plan_backend: (),
}


def validate_engine(
    plan: execution_plan.ExecutionPlan,
    backend: backend_module.DataFrameBackend,
) -> None:
    """Run engine-configuration checks in prerequisite order.

    Args:
        plan: Plan to validate against the configured backend.
        backend: Backend selected for engine execution.

    Raises:
        ValueError: A plan is incompatible with the configured engine.
        graphlib.CycleError: Validator dependencies contain a configuration cycle.
    """
    ordered = tuple(graphlib.TopologicalSorter(ENGINE_VALIDATION_DEPENDENCIES).static_order())
    for validate in ordered:
        validate(plan, backend)
