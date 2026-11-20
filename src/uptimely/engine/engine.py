"""Execution engine for plans in validated project build bundles."""

import logging
import pathlib
import time
from collections import abc

from uptimely import plan as plan_module
from uptimely.application import config as project_config
from uptimely.build import models as build_models
from uptimely.codebase.python import codebase as codebase_module
from uptimely.codebase.python import entrypoint as entrypoint_module
from uptimely.project import source_environment
from uptimely.run import recording

from . import config as config_module
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
        config: config_module.EngineConfig | None = None,
        parameters: abc.Mapping[str, object] | None = None,
        *,
        paths: abc.Mapping[str, str] | None = None,
        project_settings: project_config.ProjectSettings | None = None,
    ) -> None:
        """Prepare an engine using bundle resources and runtime configuration."""
        if not isinstance(bundle, build_models.BuildBundle):
            raise ValueError("bundle must be a BuildBundle")
        self.bundle = bundle
        self.plan = bundle.execution_plan
        self.spec_definition = bundle.spec_definition
        self.config = config_module.EngineConfig() if config is None else config
        self.parameters = project_config.Params.model_validate(
            {} if parameters is None else dict(parameters)
        ).root
        self.paths = project_config.Paths.model_validate({} if paths is None else dict(paths)).root
        self.project_settings = (
            project_config.ProjectSettings() if project_settings is None else project_settings
        )
        self.backend = backend_module.create_backend(self.config.backend)
        self.check_plan_backend()

    def check_plan_backend(self) -> None:
        """Require the configured backend to support the saved plan.

        Raises:
            ValueError: The plan requires a different dataframe backend.
        """
        logger.debug(
            "Check plan backend compatibility: required=%s, configured=%s",
            self.plan.required_backend,
            self.backend.name,
        )
        if self.plan.required_backend != self.backend.name:
            raise ValueError(
                f"Unsupported plan backend: {self.plan.required_backend}. "
                f"Expected {self.backend.name}."
            )

    def run(
        self,
        *,
        validate: bool = False,
        preview_rows: int | None = None,
        operator: tuple[str, str] | None = None,
        src_path: pathlib.Path | None = None,
    ) -> result_module.ExecutionResult:
        """Execute the plan and overwrite the project's latest-run artifacts.

        Args:
            validate: Validate inputs and dataframe contracts at every step.
                Lazy value checks may execute upstream queries repeatedly.
            preview_rows: Positive maximum sample size per profile. Defaults to the
                Engine config value. Lazy previews execute bounded queries after
                execution; timing excludes previews.
            operator: Optional (profile ID, operator ID) selecting an operator
                and its saved prerequisites, without downstream sinks. An
                explicitly selected sink still runs. Unselected invocations
                are recorded as skipped.
            src_path: Optional source directory, relative to the project root unless absolute.
                Defaults to the project source path.

        Returns:
            Main dataframes, invocation results, execution duration, collected
            preview frames, and separately reported preview failures.

        Raises:
            OSError: Run artifacts cannot be persisted.
            ValueError: The preview row limit is invalid.
                The requested operator is absent from the saved execution scope.
        """
        if preview_rows is None:
            preview_rows = self.config.preview_rows
        if src_path is None and self.project_settings.src_path is not None:
            src_path = pathlib.Path(self.project_settings.src_path)
        plan = self.plan if operator is None else self.plan.for_operator(*operator)
        with (
            source_environment.project_source_path(self.bundle.project_root, src_path=src_path),
            recording.RunRecorder(
                self.bundle, self.config, validate=validate, preview_rows=preview_rows
            ) as recorder,
        ):
            return recorder.finish(self._execute(validate=validate, plan=plan))

    def _execute(
        self, *, validate: bool, plan: plan_module.ExecutionPlan | None = None
    ) -> result_module.ExecutionResult:
        """Execute invocations without coupling runtime state to artifact storage."""
        plan = self.plan if plan is None else plan
        state = state_module.RuntimeState()
        invocation_by_entrypoint = {
            invocation.entrypoint: invocation for invocation in plan.invocations
        }
        packages: dict[str, entrypoint_module.PackageOrigin] = {}
        for location, invocation in invocation_by_entrypoint.items():
            package = invocation.package
            if package is not None:
                packages[location] = entrypoint_module.PackageOrigin(
                    distribution=package.distribution,
                    version=package.version,
                )
        python_codebase = codebase_module.Codebase.from_locations(
            invocation_by_entrypoint,
            packages,
            entrypoint_type=entrypoint_module.Entrypoint,
        )
        invocation_executor = execution_module.InvocationExecutor(
            self.backend,
            python_codebase.entrypoints_index,
            self.parameters,
            state,
            paths=self.paths,
            project_root=self.bundle.project_root,
            validate=validate,
        )
        statuses: dict[str, result_module.InvocationStatus] = {}
        durations: dict[str, float] = {}
        failures: dict[str, str] = {}

        logger.debug(
            "Executing plan with %d stages (runtime validation %s)",
            len(plan.execution_stages),
            "enabled" if validate else "disabled",
        )
        for invocation in plan.execution_invocations:
            started = time.perf_counter()
            try:
                logger.debug(
                    "Executing operator %s, function %s (role=%s, result=%s)",
                    invocation.operator_id,
                    invocation.function_id,
                    invocation.role,
                    invocation.result,
                    extra={"invocation_id": invocation.id, "profile_id": invocation.profile_id},
                )
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
                    extra={"invocation_id": invocation.id, "profile_id": invocation.profile_id},
                )
                break
            statuses[invocation.id] = result_module.INVOCATION_STATUS_SUCCEEDED
            durations[invocation.id] = time.perf_counter() - started

        for invocation in self.plan.invocations:
            statuses.setdefault(invocation.id, result_module.INVOCATION_STATUS_SKIPPED)

        return result_module.ExecutionResult(
            datasets={key: frame.dataframe for key, frame in state.datasets.items()},
            calculated_outputs=dict(state.calculated_outputs),
            invocation_statuses=statuses,
            durations=durations,
            failures=failures,
            plan_version=self.plan.plan_version,
        )
