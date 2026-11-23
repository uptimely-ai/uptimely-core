"""Execution engine for plans in validated project build bundles."""

import logging
import pathlib
import time
from collections import abc

from uptimely.application import config as project_config
from uptimely.build import models as build_models
from uptimely.codebase.python import codebase, entrypoint, packaging
from uptimely.codebase.python import runtime as python_runtime
from uptimely.project import config as code_config
from uptimely.project import python_imports
from uptimely.run import recording

from . import config as config_module
from .dataframe import backend
from .runtime import execution, result, validation
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
        code_settings: code_config.CodeSettings | None = None,
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
        self.code_settings = code_config.CodeSettings() if code_settings is None else code_settings
        self.backend = backend.create_backend(self.config.backend)
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
    ) -> result.ExecutionResult:
        """Execute the plan and overwrite the project's latest-run artifacts.

        Args:
            validate: Check invocation inputs and outputs against their analytical
                contracts. Lazy checks may execute upstream queries repeatedly.
            preview_rows: Positive maximum sample size per profile. Defaults to the
                Engine config value. Lazy previews execute bounded queries after
                execution; timing excludes previews.
            operator: Request targeted execution, which is not yet supported.
            src_path: Optional source directory, relative to the project root unless absolute.
                Defaults to bundled source, then configured or default project source.

        Returns:
            Dataset aliases, invocation statuses, execution duration, collected
            preview frames, and separately reported preview failures. Calculated
            feature outputs are unavailable and reported as None.

        Raises:
            NotImplementedError: Targeted execution was requested.
            OSError: Run artifacts cannot be persisted.
            ValueError: The preview row limit is invalid.
                The Python runtime requirements are invalid or not satisfied.
        """
        if operator is not None:
            raise NotImplementedError("Targeted execution is not yet supported")
        if preview_rows is None:
            preview_rows = self.config.preview_rows
        if src_path is None:
            src_path, source_origin = self._default_source()
        else:
            source_origin = "explicit override"
        code = self.bundle.manifest.artifacts.code
        if code.language != packaging.RUNTIME_TYPE:
            raise ValueError(f"Unsupported project runtime: {code.language}")
        if code.requirements is not None:
            if self.bundle.requirements_file is None:
                raise ValueError("Project runtime definition is missing")
            python_runtime.check_compatibility(self.bundle.requirements_file)
        with (
            python_imports.expose(self.bundle.project_root, src_path=src_path),
            recording.RunRecorder(
                self.bundle, self.config, validate=validate, preview_rows=preview_rows
            ) as recorder,
        ):
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "Selected Python source directory (%s): %s",
                    source_origin,
                    python_imports.resolve_src_path(self.bundle.project_root, src_path),
                )
            return recorder.finish(self._execute(validate=validate))

    def _default_source(self) -> tuple[pathlib.Path | None, str]:
        """Return the default Python source path and its origin for logging."""
        if (bundled_source := self.bundle.source_path) is not None:
            return bundled_source, "bundle"
        if self.code_settings.src is not None:
            return pathlib.Path(self.code_settings.src), "project configuration"
        return None, "default project source"

    def _execute(self, *, validate: bool) -> result.ExecutionResult:
        """Execute invocations without coupling runtime state to artifact storage."""
        plan = self.plan
        state = state_module.RuntimeState()
        python_codebase = codebase.Codebase.from_locations(
            plan.entrypoints,
            entrypoint_type=entrypoint.Entrypoint,
        )
        invocation_executor = execution.InvocationExecutor(
            python_codebase.entrypoints_index,
            self.parameters,
            state,
            paths=self.paths,
            project_root=self.bundle.project_root,
        )
        validator = validation.InvocationValidator(self.backend) if validate else None
        statuses: dict[str, result.InvocationStatus] = {}
        durations: dict[str, float] = {}
        failures: dict[str, str] = {}

        logger.debug(
            "Executing plan with %d stages",
            len(plan.execution_stages),
        )
        if validate:
            logger.info("Analytical runtime validation enabled")
        for invocation in plan.execution_invocations:
            started = time.perf_counter()
            try:
                logger.debug(
                    "Executing invocation %s (%s)",
                    invocation.id,
                    invocation.entrypoint,
                    extra={
                        "invocation_id": invocation.id,
                        "profile_id": (
                            invocation.semantics.profile_id if invocation.semantics else None
                        ),
                    },
                )
                arguments = invocation_executor.resolve_arguments(invocation)
                context = validator.before(invocation, arguments) if validator is not None else None
                value = invocation_executor.execute(invocation, arguments)
                if validator is not None:
                    assert context is not None
                    validator.after(invocation, value, context)
                if invocation.returns is not None:
                    state.store(invocation.returns, value)
            except Exception as error:
                statuses[invocation.id] = result.INVOCATION_STATUS_FAILED
                failures[invocation.id] = str(error)
                durations[invocation.id] = time.perf_counter() - started
                logger.warning(
                    "Invocation %s failed: %s",
                    invocation.id,
                    error,
                    exc_info=True,
                    extra={
                        "invocation_id": invocation.id,
                        "profile_id": (
                            invocation.semantics.profile_id if invocation.semantics else None
                        ),
                    },
                )
                break
            statuses[invocation.id] = result.INVOCATION_STATUS_SUCCEEDED
            durations[invocation.id] = time.perf_counter() - started

        for invocation in self.plan.invocations:
            statuses.setdefault(invocation.id, result.INVOCATION_STATUS_SKIPPED)

        return result.ExecutionResult(
            datasets={
                name: state.values[reference]
                for name, reference in plan.datasets.items()
                if reference in state.values
            },
            calculated_outputs=None,
            invocation_statuses=statuses,
            durations=durations,
            failures=failures,
            plan_version=self.plan.plan_version,
        )
