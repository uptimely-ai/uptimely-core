"""Execution engine for plans in validated project build bundles."""

import logging
import time
from collections import abc

from uptimely import project_paths
from uptimely.project.build import models as build_models
from uptimely.run import recording

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
        validation_module.EngineValidator(self.plan, self.backend).validate()

    def run(
        self, *, validate: bool = False, preview_rows: int = config_module.DEFAULT_PREVIEW_ROWS
    ) -> result_module.ExecutionResult:
        """Execute the plan and overwrite the project's latest-run artifacts.

        Args:
            validate: Validate inputs and dataframe contracts at every step.
                Lazy value checks may execute upstream queries repeatedly.
            preview_rows: Positive maximum sample size per profile. Lazy previews
                execute bounded queries after execution; timing excludes previews.

        Returns:
            Main dataframes, invocation results, execution duration, collected
            preview frames, and separately reported preview failures.

        Raises:
            OSError: Run artifacts cannot be persisted.
            ValueError: The preview row limit is invalid.
        """
        with recording.RunRecorder(
            self.bundle, self.config, validate=validate, preview_rows=preview_rows
        ) as recorder:
            return recorder.finish(self._execute(validate=validate))

    def _execute(self, *, validate: bool) -> result_module.ExecutionResult:
        """Execute invocations without coupling runtime state to artifact storage."""
        state = state_module.RuntimeState()
        invocation_executor = execution_module.InvocationExecutor(
            self.backend,
            self.plan.entrypoints_by_id,
            self.parameters,
            state,
            validate=validate,
        )
        statuses: dict[str, result_module.InvocationStatus] = {}
        durations: dict[str, float] = {}
        failures: dict[str, str] = {}

        logger.debug(
            "\nExecution plan: %d stages (runtime validation %s)",
            len(self.plan.execution_stages),
            "enabled" if validate else "disabled",
        )
        for invocation in self.plan.execution_invocations:
            started = time.perf_counter()
            logger.debug(
                "\nInvocation: %s [%s]",
                invocation.operator_id,
                invocation.function_kind,
                extra={"invocation_id": invocation.id, "profile_id": invocation.dataset_id},
            )
            if invocation.function_id != invocation.operator_id:
                logger.debug("  Function: %s", invocation.function_id)
            try:
                invocation_executor.execute(invocation)
            except Exception as error:
                statuses[invocation.id] = result_module.INVOCATION_STATUS_FAILED
                failures[invocation.id] = str(error)
                durations[invocation.id] = time.perf_counter() - started
                logger.warning(
                    "Invocation %s failed: %s",
                    invocation.id,
                    error,
                    exc_info=True,
                    extra={"invocation_id": invocation.id, "profile_id": invocation.dataset_id},
                )
                break
            statuses[invocation.id] = result_module.INVOCATION_STATUS_SUCCEEDED
            durations[invocation.id] = time.perf_counter() - started

        for invocation in self.plan.invocations:
            statuses.setdefault(invocation.id, result_module.INVOCATION_STATUS_SKIPPED)

        return result_module.ExecutionResult(
            main_frames={key: frame.dataframe for key, frame in state.main_frames.items()},
            calculated_outputs=dict(state.calculated_outputs),
            invocation_statuses=statuses,
            durations=durations,
            failures=failures,
            plan_version=self.plan.plan_version,
        )
