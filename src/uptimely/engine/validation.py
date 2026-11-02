"""Validate engine configuration against a portable execution plan."""

from __future__ import annotations

import dataclasses

from uptimely import execution_plan
from uptimely.engine.dataframe import backend as backend_module


@dataclasses.dataclass(frozen=True)
class EngineValidator:
    """Validate a portable execution plan against the configured backend."""

    plan: execution_plan.ExecutionPlan
    backend: backend_module.DataFrameBackend

    def validate(self) -> None:
        """Check that the configured engine can execute the plan.

        Raises:
            ValueError: The plan is incompatible with the configured backend.
        """
        self._validate_plan_backend()

    def _validate_plan_backend(self) -> None:
        """Require the engine backend to match the saved plan."""
        if self.plan.required_backend != self.backend.name:
            raise ValueError(
                f"Unsupported plan backend: {self.plan.required_backend}. "
                f"Expected {self.backend.name}."
            )
