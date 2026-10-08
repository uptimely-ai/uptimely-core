"""Execution engine for portable analytics plans."""

import logging
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from uptimely.compile import Compiler
from uptimely.plan import ExecutionPlan, Operation
from uptimely.spec.json_spec.bindings import is_aggregation_entry
from uptimely.spec.json_spec.json_model import Specification

from .backend import (
    CallableLoader,
    DataFrameBackend,
    EntrypointLoader,
    PlanResourceResolver,
    PolarsBackend,
    ResourceResolver,
)
from .result import ExecutionResult

logger = logging.getLogger(__name__)


@dataclass
class Calculation:
    """Runtime state of one evaluated calculated feature."""

    node: Operation
    element: object = None


@dataclass(frozen=True)
class EngineConfig:
    """Runtime configuration supplied to an execution engine."""

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
    """Execute a portable plan without recompiling its specification."""

    def __init__(
        self,
        plan: ExecutionPlan | str | Path | Specification,
        resources: dict[str, Any] | ExecutionPlan | None = None,
        *,
        config: EngineConfig | None = None,
        backend: DataFrameBackend | None = None,
        resource_resolver: ResourceResolver | None = None,
        callable_loader: CallableLoader | None = None,
        runtime_resources: dict[str, dict[str, dict[str, Any]]] | None = None,
    ) -> None:
        """Prepare an engine from a plan, with specification convenience support."""
        self._specification: Specification | None = None
        if isinstance(plan, ExecutionPlan):
            self.plan = plan
        elif isinstance(resources, ExecutionPlan):
            self.plan = resources
            if isinstance(plan, Specification):
                self._verify_specification_version(plan.version)
        elif isinstance(plan, (str, Path, Specification)):
            self._specification = (
                Specification.from_json(plan) if isinstance(plan, (str, Path)) else plan
            )
            self.plan = Compiler(self._specification).compile()
        else:
            raise ValueError("plan must be an ExecutionPlan, specification, or specification path")

        self.resources = dict(self.plan.plan.resources)
        if isinstance(resources, dict):
            self.resources.update(resources)
        self.config = config or EngineConfig()
        self.backend = backend or PolarsBackend()
        self.resource_resolver = resource_resolver or PlanResourceResolver(self.resources)
        self.callable_loader = callable_loader or EntrypointLoader()
        self._runtime_datasets: dict[tuple[str, str], object] = {}
        self._runtime_fragments: dict[tuple[str, str], object] = {}
        self._runtime_calculations: dict[tuple[str, str, str], Calculation] = {}
        self.runtime_resources = runtime_resources or {}
        self._verify_plan()

    @classmethod
    def from_specification(
        cls,
        specification: str | Path | Specification,
        features: list[str] | None = None,
        *,
        config: EngineConfig | None = None,
    ) -> "Engine":
        """Compile a specification and return an engine for the resulting plan."""
        return cls(
            Compiler(specification, features=features).compile(),
            config=config,
        )

    @property
    def callable_order(self) -> list[Operation]:
        """Return operations in execution order."""
        return self.plan.execution_order

    @property
    def specification(self) -> Specification:
        """Return the convenience specification when one was supplied."""
        if self._specification is None:
            raise AttributeError("Portable-plan engines do not retain a Specification")
        return self._specification

    @property
    def datasets(self) -> dict[tuple[str, str], object]:
        """Compatibility access to the current runtime dataset registry."""
        return self._runtime_datasets

    @datasets.setter
    def datasets(self, value: dict[tuple[str, str], object]) -> None:
        self._runtime_datasets = value

    @property
    def calculations(self) -> dict[tuple[str, str, str], Calculation]:
        """Compatibility access to calculations from the latest execution."""
        return self._runtime_calculations

    def _verify_plan(self) -> None:
        """Verify that this runtime supports the portable plan."""
        if self.plan.plan.required_backend != self.backend.name:
            raise ValueError(
                f"Unsupported plan backend: {self.plan.plan.required_backend}. "
                f"Expected {self.backend.name}."
            )
        resource_version = self.resources.get("specification_version")
        self._verify_specification_version(resource_version)

    def _verify_specification_version(self, version: str | None) -> None:
        """Verify the plan and supplied resource specification versions agree."""
        if version != self.plan.plan.specification_version:
            raise ValueError(
                "Specification version mismatch: "
                f"plan={self.plan.plan.specification_version!r}, resources={version!r}"
            )

    def execute(self) -> ExecutionResult:
        """Execute plan stages and return explicit runtime state and statuses."""
        datasets: dict[tuple[str, str], object] = {}
        fragments: dict[tuple[str, str], object] = {}
        calculations: dict[tuple[str, str, str], Calculation] = {}
        statuses: dict[str, str] = {}
        durations: dict[str, float] = {}
        failures: dict[str, str] = {}
        self._runtime_datasets = datasets
        self._runtime_fragments = fragments
        self._runtime_calculations = calculations

        def _mark_unrun_operations_skipped() -> None:
            """Mark operations that never ran so consumers can distinguish skipped from absent."""
            for operation in self.plan.execution_order:
                statuses.setdefault(operation.id, "skipped")

        logger.info("Executing plan: %d stages", len(self.plan.execution_stages))
        for stage in self.plan.execution_stages:
            for operation in stage:
                started = perf_counter()
                logger.debug("Running %s operation %s", operation.kind, operation.id)
                try:
                    if operation.kind in {"read", "collapse", "expand", "conform"}:
                        self._execute_source(operation)
                    elif operation.kind == "vectorize":
                        self._execute_calculation(operation)
                    elif operation.kind == "write":
                        self._execute_sink(operation)
                    else:
                        raise ValueError(f"Unsupported operation type: {operation.kind}")
                except Exception as error:
                    statuses[operation.id] = "failed"
                    failures[operation.id] = str(error)
                    durations[operation.id] = perf_counter() - started
                    logger.warning("Operation %s failed: %s", operation.id, error)
                    break
                statuses[operation.id] = "succeeded"
                durations[operation.id] = perf_counter() - started
            if failures:
                break

        _mark_unrun_operations_skipped()

        return ExecutionResult(
            datasets=dict(datasets),
            calculated_outputs={
                key: calculation.element for key, calculation in calculations.items()
            },
            operation_statuses=statuses,
            durations=durations,
            failures=failures,
            plan_version=self.plan.plan.plan_version,
        )

    def _execute_source(self, operation: Operation) -> None:
        """Run a fragment operation and merge its columns into the dataset."""
        frame = self.datasets.get((operation.entity_id, operation.dataset_id))
        kwargs = self._resolve_args(operation, dataset_frame=frame)
        result = self.callable_loader.load(operation.entrypoint)(**kwargs)
        self._runtime_fragments[(operation.entity_id, operation.output or operation.id)] = result
        self.datasets[(operation.entity_id, operation.dataset_id)] = self._merge_fragment(
            operation, result
        )

    def _merge_fragment(self, operation: object, fragment: object) -> object:
        """Validate and merge a fragment using its entity dimension keys."""
        function_id = getattr(operation, "function_id", "fragment")
        if not self.backend.is_frame(fragment):
            raise ValueError(f"Fragment {function_id} must return a Polars DataFrame or LazyFrame")
        entity_id = getattr(operation, "entity_id", operation.entity)
        dimensions = self.resource_resolver.entity_dimensions(entity_id)
        self._validate_fragment_keys(operation, fragment, dimensions)
        dataset_id = operation.dataset_id
        key = (entity_id, dataset_id)
        existing = self.datasets.get(key)
        if existing is None:
            return fragment
        if not self.backend.is_frame(existing):
            raise ValueError(f"Dataset {dataset_id} is not a dataframe")
        self._validate_fragment_keys(operation, existing, dimensions)
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
        self, operation: object, fragment: object, dimensions: list[str]
    ) -> None:
        """Validate the dimension-key contract of one dataframe fragment."""
        function_id = getattr(operation, "function_id", "fragment")
        columns = set(self.backend.column_names(fragment))
        missing = sorted(set(dimensions) - columns)
        if missing:
            raise ValueError(
                f"Fragment {function_id} is missing dimension columns: " + ", ".join(missing)
            )
        keys = self.backend.select(fragment, dimensions)
        if not isinstance(keys, type(fragment)):
            keys = self.backend.collect(keys)
        if self.backend.is_duplicated(keys):
            raise ValueError(f"Fragment {function_id} contains duplicate dimension keys")

    def _execute_calculation(self, operation: Operation) -> None:
        """Run a calculation and append its resulting column to the dataset."""
        dataset_key = (operation.entity_id, operation.dataset_id)
        kwargs = self._resolve_args(operation, dataset_key=dataset_key)
        result = self.callable_loader.load(operation.entrypoint)(**kwargs)
        output = operation.output or operation.function_id
        element = self._as_column(result, output)
        self.datasets[dataset_key] = self.backend.with_columns(self.datasets[dataset_key], element)
        self._runtime_calculations[(*dataset_key, output)] = Calculation(operation, element)

    def _execute_sink(self, operation: Operation) -> None:
        """Persist the selected columns of the accumulated dataset."""
        frame = self.datasets[(operation.entity_id, operation.dataset_id)]
        kwargs = self._resolve_args(
            operation, dataset_frame=frame, dataset_key=(operation.entity_id, operation.dataset_id)
        )
        self.callable_loader.load(operation.entrypoint)(**kwargs)

    def _resolve_args(
        self,
        operation: Operation,
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
            return self._dataframe_by_id(value)
        if isinstance(value, str) and value.startswith("?"):
            return self._resolve_runtime_reference(value)
        if isinstance(value, list):
            return [
                item
                for item in (
                    self._resolve_value(item, dataset_frame, dataset_key) for item in value
                )
                if item is not None
            ]
        if isinstance(value, dict):
            if value and all(is_aggregation_entry(item) for item in value.values()):
                return {
                    identifier: self._as_column(
                        self._resolve_aggregation(item, dataset_frame, dataset_key), identifier
                    )
                    for identifier, item in value.items()
                }
            return {
                name: self._resolve_value(item, dataset_frame, dataset_key)
                for name, item in value.items()
            }
        return value

    def _resolve_runtime_reference(self, value: str) -> object:
        """Resolve a `?<namespace>.<object>.<attribute>` runtime placeholder."""
        parts = value.removeprefix("?").split(".")
        if len(parts) != 3:
            raise ValueError(f"Malformed runtime reference: {value}")
        namespace, object_id, attribute = parts
        namespace_resources = self.runtime_resources.get(namespace)
        if namespace_resources is None:
            raise ValueError(f"Unknown runtime namespace: {namespace}")
        object_resources = namespace_resources.get(object_id)
        if object_resources is None:
            raise ValueError(f"Unknown {namespace} object: {object_id}")
        if attribute not in object_resources:
            raise ValueError(f"{namespace} object {object_id} has no attribute: {attribute}")
        return object_resources[attribute]

    def _resolve_aggregation(
        self, value: object, dataset_frame: object, dataset_key: tuple[str, str] | None
    ) -> object:
        """Resolve and invoke an aggregate binding used by a collapse operation."""
        if not isinstance(value, dict) or not isinstance(value.get("function"), str):
            raise ValueError("aggregation must contain function and args")
        entrypoint = self.resource_resolver.function_entrypoint("aggregate", value["function"])
        arguments = self.resources["functions"]["aggregate"][value["function"]].get("args", {})
        kwargs = {
            name: self._resolve_value(
                argument, dataset_frame, dataset_key, arguments.get(name, {}).get("type")
            )
            for name, argument in value.get("args", {}).items()
        }
        return self.callable_loader.load(entrypoint)(**kwargs)

    def _feature_value(
        self, feature: str, dataset_frame: object, dataset_key: tuple[str, str] | None
    ) -> object | None:
        calculation = (
            self._runtime_calculations.get((*dataset_key, feature))
            if dataset_key is not None
            else None
        )
        if calculation is not None:
            return calculation.element
        if dataset_frame is None:
            return self.backend.feature_column(feature)
        return (
            self.backend.feature_column(feature)
            if feature in self.backend.column_names(dataset_frame)
            else None
        )

    def _dataset_by_id(self, dataset_id: str) -> object | None:
        matches = [
            frame for (_, current_id), frame in self.datasets.items() if current_id == dataset_id
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

    def _as_column(self, element: object, feature: str) -> object:
        """Return a calculation result as a named backend column."""
        if self.backend.is_column(element):
            return self.backend.alias(element, feature)
        return self.backend.alias(self.backend.literal(element), feature)
