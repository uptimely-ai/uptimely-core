"""Execution engine for plans in validated project build bundles."""

import logging
import time
from collections import abc

from uptimely import entrypoint as entrypoint_module
from uptimely import project_paths
from uptimely.project.build import models as build_models

from . import config as config_module
from . import validation as validation_module
from .dataframe import backend as backend_module
from .runtime import execution as execution_module
from .runtime import result as result_module
from .runtime import state as state_module

logger = logging.getLogger(__name__)


class Engine:
    """Execute the plan in a validated project build bundle."""

    def __init__(
        self,
        bundle: build_models.BuildBundle,
        config: config_module.Config | config_module.EngineConfig,
        parameters: abc.Mapping[str, object] | None = None,
    ) -> None:
        """Prepare an engine using bundle resources and runtime configuration."""
        if not isinstance(bundle, build_models.BuildBundle):
            raise ValueError("bundle must be a BuildBundle")
        self.bundle = bundle
        self.plan = bundle.execution_plan
        self.spec_definition = bundle.spec_definition
        if isinstance(config, config_module.Config):
            self.config = config.engine
            configured_parameters = config.params.root
        else:
            self.config = config
            configured_parameters = self._load_parameters(bundle, parameters)
        if parameters is not None and isinstance(config, config_module.Config):
            configured_parameters = config_module.Params.model_validate(dict(parameters)).root
        self.parameters = configured_parameters
        self.backend = backend_module.create_backend(self.config.backend)
        self._validate_engine()

    @staticmethod
    def _load_parameters(
        bundle: build_models.BuildBundle,
        parameters: abc.Mapping[str, object] | None,
    ) -> dict[str, object]:
        """Validate explicit values or load parameters from the project config file."""
        if parameters is not None:
            return config_module.Params.model_validate(dict(parameters)).root
        path = bundle.project_root / project_paths.CONFIG_FILE
        if not path.is_file():
            if path.exists():
                raise ValueError(f"Parameter configuration is not a file: {path}")
            return {}
        configuration = config_module.Config.model_validate_json(path.read_text(encoding="utf-8"))
        return configuration.params.root

    def _validate_engine(self) -> None:
        """Validate that this engine can execute the plan."""
        validation_module.validate_engine(
            validation_module.EngineValidationContext(self.plan, self.backend),
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
            self.parameters,
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
