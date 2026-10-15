"""Execution engine for portable analytics plans."""

import dataclasses
import logging
import pathlib
import time
import typing

from uptimely import compile
from uptimely import plan as plan_module
from uptimely.analytics.json import json_model

from . import backend as backend_module
from . import result as result_module

logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class EngineConfig:
    """Runtime configuration supplied to an execution engine.

    ``evaluation`` and ``batch_size`` are reserved and do not currently affect
    execution.
    """

    type: str = "python_venv"
    definition: str | None = None
    dataframe: str = "polars"
    evaluation: str = "eager"
    batch_size: int | str | None = None

    def __post_init__(self) -> None:
        """Validate configuration values before execution begins."""
        if not isinstance(self.dataframe, str) or self.dataframe.lower() != "polars":
            raise ValueError(
                "Unsupported dataframe backend: "
                f"{self.dataframe}. Version 0.1 supports only polars."
            )
        if self.batch_size is not None and (
            not (
                isinstance(self.batch_size, int)
                and not isinstance(self.batch_size, bool)
                and self.batch_size > 0
            )
            and self.batch_size != "*"
        ):
            raise ValueError("batch_size must be a positive integer, '*', or None")


class Engine:
    """Execute a portable plan without recompiling its analytics definition."""

    def __init__(
        self,
        plan: plan_module.ExecutionPlan | str | pathlib.Path | json_model.Analytics,
        resources: dict[str, typing.Any] | None = None,
        *,
        config: EngineConfig | None = None,
        backend: backend_module.DataFrameBackend | None = None,
        resource_resolver: backend_module.ResourceResolver | None = None,
        callable_loader: backend_module.CallableLoader | None = None,
        bind: dict[str, dict[str, dict[str, typing.Any]]] | None = None,
    ) -> None:
        """Prepare an engine from a plan, with analytics convenience support."""
        self._analytics: json_model.Analytics | None = None
        if isinstance(plan, plan_module.ExecutionPlan):
            self.plan = plan
        elif isinstance(plan, (str, pathlib.Path, json_model.Analytics)):
            self._analytics = (
                json_model.Analytics(json=plan) if isinstance(plan, (str, pathlib.Path)) else plan
            )
            self.plan = compile.Compiler(self._analytics).compile()
        else:
            raise ValueError("plan must be an ExecutionPlan, Analytics, or analytics path")

        self.resources = dict(self.plan.plan.resources)
        if resources is not None:
            if not isinstance(resources, dict):
                raise TypeError("resources must be a dictionary of plan resource overrides")
            self.resources.update(resources)
        self.config = config or EngineConfig()
        self.backend = backend or backend_module.PolarsBackend()
        self.resource_resolver = resource_resolver or backend_module.PlanResourceResolver(
            self.resources
        )
        self.callable_loader = callable_loader or backend_module.EntrypointLoader()
        self._runtime_datasets: dict[tuple[str, str], object] = {}
        self._runtime_fragments: dict[tuple[str, str], object] = {}
        self._runtime_calculations: dict[tuple[str, str, str], object] = {}
        self.bind = bind or {}
        self._verify_plan()

    @classmethod
    def from_analytics(
        cls,
        analytics_definition: str | pathlib.Path | json_model.Analytics,
        features: list[str] | None = None,
        *,
        config: EngineConfig | None = None,
    ) -> "Engine":
        """Compile analytics and return an engine for the resulting plan."""
        return cls(
            compile.Compiler(analytics_definition, features=features).compile(),
            config=config,
        )

    @property
    def analytics(self) -> json_model.Analytics:
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
        resource_version = self.resources.get("specification_version")
        self._verify_analytics_version(resource_version)

    def _verify_analytics_version(self, version: str | None) -> None:
        """Verify the plan and supplied resource analytics versions agree."""
        if version != self.plan.plan.specification_version:
            raise ValueError(
                "Analytics version mismatch: "
                f"plan={self.plan.plan.specification_version!r}, resources={version!r}"
            )

    def execute(self) -> result_module.ExecutionResult:
        """Execute plan stages and return explicit runtime state and statuses."""
        datasets: dict[tuple[str, str], object] = {}
        fragments: dict[tuple[str, str], object] = {}
        calculations: dict[tuple[str, str, str], object] = {}
        statuses: dict[str, str] = {}
        durations: dict[str, float] = {}
        failures: dict[str, str] = {}
        self._runtime_datasets = datasets
        self._runtime_fragments = fragments
        self._runtime_calculations = calculations

        def _mark_unrun_operations_skipped() -> None:
            """Mark operations that never ran so consumers can distinguish skipped from absent."""
            for operation in self.plan.operations:
                statuses.setdefault(operation.id, "skipped")

        logger.info("Executing plan: %d stages", len(self.plan.execution_stages))
        for stage in self.plan.execution_stages:
            for operation in stage:
                started = time.perf_counter()
                logger.debug("Running %s operation %s", operation.kind, operation.id)
                try:
                    self._validate_inputs(operation)
                    if operation.kind in {"read", "expand", "conform", "collapse", "vectorize"}:
                        self._execute_dataframe_mapping(operation)
                    elif operation.kind == "write":
                        self._execute_sink(operation)
                    else:
                        raise ValueError(f"Unsupported operation type: {operation.kind}")
                except Exception as error:
                    statuses[operation.id] = "failed"
                    failures[operation.id] = str(error)
                    durations[operation.id] = time.perf_counter() - started
                    logger.warning("Operation %s failed: %s", operation.id, error)
                    break
                statuses[operation.id] = "succeeded"
                durations[operation.id] = time.perf_counter() - started
            if failures:
                break

        _mark_unrun_operations_skipped()

        return result_module.ExecutionResult(
            datasets=dict(datasets),
            calculated_outputs=dict(calculations),
            operation_statuses=statuses,
            durations=durations,
            failures=failures,
            plan_version=self.plan.plan.plan_version,
        )

    def _execute_dataframe_mapping(self, operation: plan_module.Operation) -> None:
        """Invoke a data-producing mapping, validate its result, and update the dataset."""
        dataset_key = (operation.entity_id, operation.dataset_id)
        frame = self._runtime_datasets.get(dataset_key)
        kwargs = self._resolve_args(operation, dataset_frame=frame)
        result = self.callable_loader.load(operation.entrypoint)(**kwargs)
        dimensions = self.resource_resolver.entity_dimensions(operation.entity_id)
        self._validate_dataframe_result(operation, result, frame, dimensions)
        columns = list(dict.fromkeys([*dimensions, *operation.output_features]))
        fragment = self.backend.select(result, columns)
        merged = self._merge_fragment(frame, fragment, dimensions)

        self._runtime_datasets[dataset_key] = merged
        self._runtime_fragments[(operation.entity_id, operation.output or operation.id)] = fragment
        if operation.kind == "vectorize":
            for output in operation.output_features:
                self._runtime_calculations[(*dataset_key, output)] = self.backend.select(
                    fragment, [*dimensions, output]
                )

    def _validate_dataframe_result(
        self,
        operation: plan_module.Operation,
        result: object,
        input_frame: object,
        dimensions: list[str],
    ) -> None:
        """Check the returned dataframe's keys, declared outputs, and logical types."""
        if not self.backend.is_frame(result):
            raise ValueError(
                f"Fragment {operation.function_id} must return a Polars DataFrame or LazyFrame"
            )
        self._validate_fragment_keys(operation, result, dimensions)
        columns = set(self.backend.column_names(result))
        missing = sorted(set(operation.output_features) - columns)
        if missing:
            raise ValueError(
                f"Mapping {operation.id} is missing output columns: " + ", ".join(missing)
            )
        dimension_definitions = self.resources.get("dimensions", {})
        feature_definitions = (
            self.resources.get("datasets", {}).get(operation.dataset_id, {}).get("features", {})
        )
        types: dict[str, str] = {}
        for name in dict.fromkeys([*dimensions, *operation.output_features]):
            definitions = dimension_definitions if name in dimensions else feature_definitions
            column_type = definitions.get(name, {}).get("type")
            if column_type is not None:
                types[name] = column_type
        self.backend.validate_types(result, types)
        if operation.kind == "vectorize" and (
            input_frame is None or not self.backend.same_keys(input_frame, result, dimensions)
        ):
            raise ValueError(
                f"Vectorize mapping {operation.id} must preserve the dataset dimension keys"
            )

    def _validate_inputs(self, operation: plan_module.Operation) -> None:
        """Require declared input columns to be materialized before invocation."""
        for feature in operation.input_features:
            frames = [
                frame
                for frame in self._runtime_datasets.values()
                if feature in self.backend.column_names(frame)
            ]
            current = self._runtime_datasets.get((operation.entity_id, operation.dataset_id))
            if current is not None and feature in self.backend.column_names(current):
                continue
            if len(frames) != 1:
                raise ValueError(
                    f"Mapping {operation.id} input feature is unavailable or ambiguous: {feature}"
                )

    def _merge_fragment(self, existing: object, fragment: object, dimensions: list[str]) -> object:
        """Join a validated fragment without replacing existing feature columns."""
        if existing is None:
            return fragment
        existing_columns = set(self.backend.column_names(existing))
        new_columns = [
            column
            for column in self.backend.column_names(fragment)
            if column not in existing_columns and column not in dimensions
        ]
        if not new_columns:
            return existing
        right = self.backend.select(fragment, [*dimensions, *new_columns])
        left = existing
        if type(existing) is not type(right):
            left = self.backend.lazy(existing)
            right = self.backend.lazy(right)
        return self.backend.join(left, right, dimensions)

    def _validate_fragment_keys(
        self, operation: plan_module.Operation, fragment: object, dimensions: list[str]
    ) -> None:
        """Validate the dimension-key contract of one dataframe fragment."""
        columns = set(self.backend.column_names(fragment))
        missing = sorted(set(dimensions) - columns)
        if missing:
            raise ValueError(
                f"Fragment {operation.function_id} is missing dimension columns: "
                + ", ".join(missing)
            )
        if not dimensions:
            if self.backend.row_count(fragment) > 1:
                raise ValueError(
                    f"Fragment {operation.function_id} contains duplicate dimension keys "
                    "(dimensionless datasets allow at most one row)"
                )
            return
        keys = self.backend.select(fragment, dimensions)
        if not isinstance(keys, type(fragment)):
            keys = self.backend.collect(keys)
        if self.backend.is_duplicated(keys):
            raise ValueError(f"Fragment {operation.function_id} contains duplicate dimension keys")

    def _execute_sink(self, operation: plan_module.Operation) -> None:
        """Persist the selected columns of the accumulated dataset."""
        frame = self._runtime_datasets[(operation.entity_id, operation.dataset_id)]
        kwargs = self._resolve_args(
            operation, dataset_frame=frame, dataset_key=(operation.entity_id, operation.dataset_id)
        )
        self.callable_loader.load(operation.entrypoint)(**kwargs)

    def _resolve_args(
        self,
        operation: plan_module.Operation,
        dataset_frame: object = None,
        dataset_key: tuple[str, str] | None = None,
    ) -> dict[str, object]:
        """Bind compiled IDs to physical runtime arguments using template types."""
        arguments = self.resources["functions"][operation.kind][operation.function_id].get(
            "args", {}
        )
        return {
            name: self._resolve_value(
                value, dataset_frame, dataset_key, arguments.get(name, {}).get("type")
            )
            for name, value in operation.arguments.items()
        }

    def _resolve_value(
        self,
        value: object,
        dataset_frame: object,
        dataset_key: tuple[str, str] | None,
        argument_type: str | None = None,
    ) -> object:
        """Recursively resolve one typed plan binding value."""
        if hasattr(value, "model_dump"):
            value = value.model_dump()
        if argument_type == "dataframe" and isinstance(value, str):
            frame = self._dataframe_by_id(value)
            if frame is None:
                raise ValueError(f"Dataset dataframe is unavailable: {value}")
            return frame
        if isinstance(value, str) and value.startswith("?"):
            return self._resolve_runtime_reference(value)
        if isinstance(value, list):
            element_type = (
                argument_type[6:-1]
                if argument_type is not None and argument_type.startswith("array[")
                else None
            )
            return [
                self._resolve_value(item, dataset_frame, dataset_key, element_type)
                for item in value
            ]
        if isinstance(value, dict):
            value_type = (
                argument_type[12:-1]
                if argument_type is not None and argument_type.startswith("object{str: ")
                else None
            )
            return {
                name: self._resolve_value(item, dataset_frame, dataset_key, value_type)
                for name, item in value.items()
            }
        return value

    def _resolve_runtime_reference(self, value: str) -> object:
        """Resolve a `?<namespace>.<object>.<attribute>` runtime placeholder."""
        parts = value.removeprefix("?").split(".")
        if len(parts) != 3:
            raise ValueError(f"Malformed runtime reference: {value}")
        namespace, object_id, attribute = parts
        namespace_bindings = self.bind.get(namespace)
        if namespace_bindings is None:
            raise ValueError(f"Unknown runtime namespace: {namespace}")
        object_bindings = namespace_bindings.get(object_id)
        if object_bindings is None:
            raise ValueError(f"Unknown {namespace} object: {object_id}")
        if attribute not in object_bindings:
            raise ValueError(f"{namespace} object {object_id} has no attribute: {attribute}")
        return object_bindings[attribute]

    def _dataset_by_id(self, dataset_id: str) -> object | None:
        matches = [
            frame
            for (_, current_id), frame in self._runtime_datasets.items()
            if current_id == dataset_id
        ]
        if len(matches) > 1:
            raise ValueError(f"Ambiguous dataset reference: {dataset_id}")
        return matches[0] if matches else None

    def _dataframe_by_id(self, identifier: str) -> object | None:
        """Return the unique live dataset or fragment identified by a compiled binding."""
        dataset = self._dataset_by_id(identifier)
        if dataset is not None:
            return dataset
        matches = [
            frame
            for (_, fragment_id), frame in self._runtime_fragments.items()
            if fragment_id == identifier
        ]
        if len(matches) > 1:
            raise ValueError(f"Ambiguous fragment reference: {identifier}")
        return matches[0] if matches else None
