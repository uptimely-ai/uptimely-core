"""Execution engine for plans in validated project build bundles."""

import logging
import time

from uptimely import entrypoint as entrypoint_module
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
        self.plan = bundle.execution_plan
        self.spec_definition = bundle.spec_definition
        self.config = config
        self.backend = backend_module.create_backend(config.backend)
        self.bind = config.bind
        self._validate_engine()

    def _validate_engine(self) -> None:
        """Validate that this engine can execute the plan."""
        if self.plan.required_backend != self.backend.name:
            raise ValueError(
                f"Unsupported plan backend: {self.plan.required_backend}. "
                f"Expected {self.backend.name}."
            )

    def run(self) -> result_module.ExecutionResult:
        """Execute plan stages and return explicit runtime state and statuses."""
        state = state_module.RuntimeState()
        packages = self.plan.resources.get("entrypoint_packages", {})
        invocation_executor = execution_module.InvocationExecutor(
            self.backend,
            self.spec_definition,
            {
                invocation.entrypoint: entrypoint_module.Entrypoint(
                    invocation.entrypoint,
                    package=(
                        entrypoint_module.PackageProvenance(**packages[invocation.entrypoint])
                        if invocation.entrypoint in packages
                        else None
                    ),
                )
                for invocation in self.plan.invocations
            },
            self.bind,
            state,
        )
        statuses: dict[str, result_module.InvocationStatus] = {}
        durations: dict[str, float] = {}
        failures: dict[str, str] = {}

        logger.debug("Executing plan: %d stages", len(self.plan.execution_stages))
        for stage in self.plan.execution_stages:
            for invocation in stage:
                started = time.perf_counter()
                logger.debug("Running %s invocation %s", invocation.function_kind, invocation.id)
                try:
                    invocation_executor.execute(invocation)
                except Exception as error:
                    statuses[invocation.id] = result_module.INVOCATION_STATUS_FAILED
                    failures[invocation.id] = str(error)
                    durations[invocation.id] = time.perf_counter() - started
                    logger.warning("Invocation %s failed: %s", invocation.id, error)
                    break
                statuses[invocation.id] = result_module.INVOCATION_STATUS_SUCCEEDED
                durations[invocation.id] = time.perf_counter() - started
            if failures:
                break

        for invocation in self.plan.invocations:
            statuses.setdefault(invocation.id, result_module.INVOCATION_STATUS_SKIPPED)

        return result_module.ExecutionResult(
            datasets=dict(state.datasets),
            calculated_outputs=dict(state.calculated_outputs),
            invocation_statuses=statuses,
            durations=durations,
            failures=failures,
            plan_version=self.plan.plan_version,
        )
