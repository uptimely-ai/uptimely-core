"""Execution engine for plans in validated project build bundles."""

import logging
import time

from uptimely import contracts
from uptimely import entrypoint as entrypoint_module
from uptimely.compiler import plan as plan_module
from uptimely.project import imports as project_imports
from uptimely.project.build import models as build_models

from . import backend as backend_module
from . import bindings as bindings_module
from . import config as config_module
from . import dataframe as dataframe_module
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
        self.resources = self.plan.plan.resources
        self.config = config
        self.backend = backend_module.create_backend(config.backend.dataframe)
        self.bind = config.bind
        self._verify_plan()

    def _verify_plan(self) -> None:
        """Verify that this runtime supports the portable plan."""
        if self.plan.plan.required_backend != self.backend.name:
            raise ValueError(
                f"Unsupported plan backend: {self.plan.plan.required_backend}. "
                f"Expected {self.backend.name}."
            )

    def execute(self) -> result_module.ExecutionResult:
        """Execute plan stages and return explicit runtime state and statuses."""
        state = state_module.RuntimeState()
        bindings = bindings_module.RuntimeBindings(self.resources, state, self.bind)
        dataframe = dataframe_module.DataFrameExecution(self.backend, self.resources, state)
        statuses: dict[str, result_module.CallableStatus] = {}
        durations: dict[str, float] = {}
        failures: dict[str, str] = {}

        def _mark_unrun_callables_skipped() -> None:
            """Mark callables that never ran as skipped."""
            for callable in self.plan.callables:
                statuses.setdefault(callable.id, "skipped")

        logger.info("Executing plan: %d stages", len(self.plan.execution_stages))
        for stage in self.plan.execution_stages:
            for callable in stage:
                started = time.perf_counter()
                logger.debug("Running %s callable %s", callable.operation, callable.id)
                try:
                    if callable.operation == "escape":
                        self._execute_escape(callable, bindings)
                    else:
                        dataframe.validate_inputs(callable)
                        if contracts.OPERATION_RETURN_KINDS.get(callable.operation) == "dataframe":
                            self._execute_dataframe_mapping(callable, state, bindings, dataframe)
                        elif contracts.OPERATION_RETURN_KINDS.get(callable.operation) == "none":
                            self._execute_sink(callable, state, bindings)
                        else:
                            raise ValueError(
                                f"Unsupported callable operation: {callable.operation}"
                            )
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

        _mark_unrun_callables_skipped()

        return result_module.ExecutionResult(
            datasets=dict(state.datasets),
            calculated_outputs=dict(state.calculated_outputs),
            callable_statuses=statuses,
            durations=durations,
            failures=failures,
            plan_version=self.plan.plan.plan_version,
        )

    def _execute_dataframe_mapping(
        self,
        callable: plan_module.Callable,
        state: state_module.RuntimeState,
        bindings: bindings_module.RuntimeBindings,
        dataframe: dataframe_module.DataFrameExecution,
    ) -> None:
        """Invoke a data-producing mapping, validate its result, and update the dataset."""
        dataset_key = (callable.entity_id, callable.dataset_id)
        frame = state.datasets.get(dataset_key)
        kwargs = bindings.resolve_args(callable)
        result = entrypoint_module.Entrypoint(
            callable.entrypoint, self.bundle.project_root
        ).function.load()(**kwargs)
        entity = self.resources.get("entities", {}).get(callable.entity_id)
        if entity is None:
            raise ValueError(f"Unknown entity: {callable.entity_id}")
        dimensions = list(entity.get("dimensions", []))
        dataframe.validate_result(callable, result, frame, dimensions)
        columns = list(dict.fromkeys([*dimensions, *callable.output_features]))
        fragment = self.backend.select(result, columns)
        merged = dataframe.merge_fragment(frame, fragment, dimensions)

        state.datasets[dataset_key] = merged
        state.fragments[(callable.entity_id, callable.output or callable.id)] = fragment
        if callable.operation == "vectorize":
            for output in callable.output_features:
                state.calculated_outputs[(*dataset_key, output)] = self.backend.select(
                    fragment, [*dimensions, output]
                )

    def _execute_escape(
        self,
        callable: plan_module.Callable,
        bindings: bindings_module.RuntimeBindings,
    ) -> None:
        """Invoke an uncontrolled mapping and discard its return value."""
        kwargs = bindings.resolve_args(callable)
        entrypoint_module.Entrypoint(callable.entrypoint, self.bundle.project_root).function.load()(
            **kwargs
        )

    def _execute_sink(
        self,
        callable: plan_module.Callable,
        state: state_module.RuntimeState,
        bindings: bindings_module.RuntimeBindings,
    ) -> None:
        """Persist the selected columns of the accumulated dataset."""
        dataset_key = (callable.entity_id, callable.dataset_id)
        if dataset_key not in state.datasets:
            raise KeyError(dataset_key)
        kwargs = bindings.resolve_args(callable)
        entrypoint_module.Entrypoint(callable.entrypoint, self.bundle.project_root).function.load()(
            **kwargs
        )
