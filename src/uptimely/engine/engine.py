"""Execution engine for portable analytics plans."""

import logging
import pathlib
import time
import typing

from uptimely import analytics, contracts
from uptimely import compiler as compiler_module
from uptimely.analytics import model as analytics_model
from uptimely.compiler import plan as plan_module

from . import backend as backend_module
from . import bindings as bindings_module
from . import config as config_module
from . import dataframe as dataframe_module
from . import result as result_module
from . import state as state_module

logger = logging.getLogger(__name__)


class Engine:
    """Execute a portable plan without recompiling its analytics definition."""

    def __init__(
        self,
        plan: plan_module.ExecutionPlan | str | pathlib.Path | analytics_model.Analytics,
        resources: dict[str, typing.Any] | None = None,
        *,
        config: config_module.EngineConfig | None = None,
        backend: backend_module.DataFrameBackend | None = None,
        resource_resolver: backend_module.ResourceResolver | None = None,
        callable_loader: backend_module.CallableLoader | None = None,
        bind: dict[str, dict[str, dict[str, typing.Any]]] | None = None,
    ) -> None:
        """Prepare an engine from a plan, with analytics convenience support."""
        self._analytics: analytics_model.Analytics | None = None
        if isinstance(plan, plan_module.ExecutionPlan):
            self.plan = plan
        elif isinstance(plan, (str, pathlib.Path, analytics_model.Analytics)):
            self._analytics = (
                analytics.load_analytics(plan) if isinstance(plan, (str, pathlib.Path)) else plan
            )
            self.plan = compiler_module.Compiler(self._analytics).compile()
        else:
            raise ValueError("plan must be an ExecutionPlan, Analytics, or analytics path")

        self.resources = dict(self.plan.plan.resources)
        if resources is not None:
            if not isinstance(resources, dict):
                raise TypeError("resources must be a dictionary of plan resource overrides")
            self.resources.update(resources)
        self.config = config or config_module.EngineConfig()
        self.backend = backend or backend_module.PolarsBackend()
        self.resource_resolver = resource_resolver or backend_module.PlanResourceResolver(
            self.resources
        )
        self.callable_loader = callable_loader or backend_module.EntrypointLoader()
        self.bind = bind or {}
        self._verify_plan()

    @classmethod
    def from_analytics(
        cls,
        analytics_definition: str | pathlib.Path | analytics_model.Analytics,
        features: list[str] | None = None,
        *,
        config: config_module.EngineConfig | None = None,
    ) -> "Engine":
        """Compile analytics and return an engine for the resulting plan."""
        return cls(
            compiler_module.Compiler(analytics_definition, features=features).compile(),
            config=config,
        )

    @property
    def analytics(self) -> analytics_model.Analytics:
        """Return the Analytics instance when one was supplied."""
        if self._analytics is None:
            raise AttributeError("Portable-plan engines do not retain an Analytics instance")
        return self._analytics

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
                    dataframe.validate_inputs(callable)
                    if contracts.OPERATION_RETURN_KINDS.get(callable.operation) == "dataframe":
                        self._execute_dataframe_mapping(callable, state, bindings, dataframe)
                    elif contracts.OPERATION_RETURN_KINDS.get(callable.operation) == "none":
                        self._execute_sink(callable, state, bindings)
                    else:
                        raise ValueError(f"Unsupported callable operation: {callable.operation}")
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
        result = self.callable_loader.load(callable.entrypoint)(**kwargs)
        dimensions = self.resource_resolver.entity_dimensions(callable.entity_id)
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
        self.callable_loader.load(callable.entrypoint)(**kwargs)
