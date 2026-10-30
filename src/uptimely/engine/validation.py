"""Validate engine configuration against a portable execution plan."""

from __future__ import annotations

import collections.abc
import dataclasses
import graphlib

from uptimely import execution_plan
from uptimely.engine.dataframe import backend as backend_module


@dataclasses.dataclass(frozen=True)
class EngineValidationContext:
    """Plan and backend values used to validate engine configuration."""

    plan: execution_plan.ExecutionPlan
    backend: backend_module.DataFrameBackend


type Validator = collections.abc.Callable[[EngineValidationContext], None]


def validate_plan_backend(context: EngineValidationContext) -> None:
    """Require the engine backend to match the saved plan."""
    if context.plan.required_backend != context.backend.name:
        raise ValueError(
            f"Unsupported plan backend: {context.plan.required_backend}. "
            f"Expected {context.backend.name}."
        )


ENGINE_VALIDATION_DEPENDENCIES: dict[Validator, tuple[Validator, ...]] = {
    validate_plan_backend: (),
}


def validate_engine(context: EngineValidationContext) -> None:
    """Run engine-configuration checks in prerequisite order.

    Args:
        context: Plan and backend values for the engine being configured.

    Raises:
        ValueError: A plan is incompatible with the configured engine.
        graphlib.CycleError: Validator dependencies contain a configuration cycle.
    """
    ordered = tuple(graphlib.TopologicalSorter(ENGINE_VALIDATION_DEPENDENCIES).static_order())
    for validate in ordered:
        validate(context)
