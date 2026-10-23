"""Execution engine for plans in validated project build bundles."""

import logging
import time

from uptimely.project import imports as project_imports
from uptimely.project.build import models as build_models

from . import backend as backend_module
from . import config as config_module
from . import execution as execution_module
from . import result as result_module
from . import state as state_module

logger = logging.getLogger(__name__)


class Engine:
    """Execute the plan in a validated project build bundle."""

    def __init__(
        self,
        bundle: build_models.BuildBundle,
        config: config_module.EngineConfig,
    ) -> None:
        """Prepare an engine using bundle resources and runtime configuration."""
        if not isinstance(bundle, build_models.BuildBundle):
            raise ValueError("bundle must be a BuildBundle")
        self.bundle = bundle
        project_imports.prepare_imports(bundle.project_root)
        self.plan = bundle.execution_plan
        self.spec_definition = bundle.spec_definition
        self.config = config
        self.backend = backend_module.create_backend(config.backend.dataframe)
        self.bind = config.bind
        self._validate_engine()

    def _validate_engine(self) -> None:
        """Validate that this engine can execute the plan."""
        if self.plan.plan.required_backend != self.backend.name:
            raise ValueError(
                f"Unsupported plan backend: {self.plan.plan.required_backend}. "
                f"Expected {self.backend.name}."
            )

    def run(self) -> result_module.ExecutionResult:
        """Execute plan stages and return explicit runtime state and statuses."""
        state = state_module.RuntimeState()
        callable_executor = execution_module.CallableExecutor(
            self.bundle.project_root, self.backend, self.spec_definition, self.bind, state
        )
        statuses: dict[str, result_module.CallableStatus] = {}
        durations: dict[str, float] = {}
        failures: dict[str, str] = {}

        logger.debug("Executing plan: %d stages", len(self.plan.execution_stages))
        for stage in self.plan.execution_stages:
            for callable in stage:
                started = time.perf_counter()
                logger.debug("Running %s callable %s", callable.operation, callable.id)
                try:
                    callable_executor.execute(callable)
                except Exception as error:
                    statuses[callable.id] = "failed"
                    failures[callable.id] = str(error)
                    durations[callable.id] = time.perf_counter() - started
                    logger.warning("Callable %s failed: %s", callable.id, error)
                    break
                statuses[callable.id] = "succeeded"
                durations[callable.id] = time.perf_counter() - started
            if failures:
                break

        for callable in self.plan.callables:
            statuses.setdefault(callable.id, "skipped")

        return result_module.ExecutionResult(
            datasets=dict(state.datasets),
            calculated_outputs=dict(state.calculated_outputs),
            callable_statuses=statuses,
            durations=durations,
            failures=failures,
            plan_version=self.plan.plan.plan_version,
        )
