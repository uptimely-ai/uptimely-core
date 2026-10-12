"""Execution engine for portable analytics plans."""

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from uptimely.compile import Compiler
from uptimely.plan import ExecutionPlan, Operation
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
        resources: dict[str, Any] | None = None,
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
        elif isinstance(plan, (str, Path, Specification)):
            self._specification = (
                Specification.from_json(plan) if isinstance(plan, (str, Path)) else plan
            )
            self.plan = Compiler(self._specification).compile()
        else:
            raise ValueError("plan must be an ExecutionPlan, specification, or specification path")

        self.resources = dict(self.plan.plan.resources)
        if resources is not None:
            if not isinstance(resources, dict):
                raise TypeError("resources must be a dictionary of plan resource overrides")
            self.resources.update(resources)
        self.config = config or EngineConfig()
        self.backend = backend or PolarsBackend()
        self.resource_resolver = resource_resolver or PlanResourceResolver(self.resources)
        self.callable_loader = callable_loader or EntrypointLoader()
        self._runtime_datasets: dict[tuple[str, str], object] = {}
        self._runtime_fragments: dict[tuple[str, str], object] = {}
        self._runtime_calculations: dict[tuple[str, str, str], object] = {}
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
    def specification(self) -> Specification:
        """Return the convenience specification when one was supplied."""
        if self._specification is None:
            raise AttributeError("Portable-plan engines do not retain a Specification")
        return self._specification

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
                started = perf_counter()
                logger.debug("Running %s operation %s", operation.kind, operation.id)
                try:
                    if operation.kind == "collapse":
                        self._execute_collapse(operation)
                    elif operation.kind in {"read", "expand", "conform"}:
                        self._execute_source(operation)
                    elif operation.kind == "vectorize":
                        self._execute_vectorize(operation)
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
            calculated_outputs=dict(calculations),
            operation_statuses=statuses,
            durations=durations,
            failures=failures,
            plan_version=self.plan.plan.plan_version,
        )

    def _execute_source(self, operation: Operation) -> None:
        """Run a fragment operation and merge its columns into the dataset."""
        frame = self._runtime_datasets.get((operation.entity_id, operation.dataset_id))
        kwargs = self._resolve_args(operation, dataset_frame=frame)
        result = self.callable_loader.load(operation.entrypoint)(**kwargs)
        self._runtime_fragments[(operation.entity_id, operation.output or operation.id)] = result
        self._runtime_datasets[(operation.entity_id, operation.dataset_id)] = self._merge_fragment(
            operation, result
        )

    def _execute_collapse(self, operation: Operation) -> None:
        """Invoke the collapse function and group by the target entity dimensions."""
        input_datasets = {
            dependency.dataset_id
            for dependency in self.plan.operations
            if dependency.id in operation.dependency_ids
            and dependency.dataset_id != operation.dataset_id
            and dependency.kind in {"read", "conform", "expand", "collapse", "vectorize"}
            and dependency.dataset_id is not None
        }
        if len(input_datasets) != 1:
            raise ValueError(
                f"Collapse {operation.id} dependencies must identify one input dataset"
            )
        source_id = next(iter(input_datasets))
        source = self._dataset_by_id(source_id)
        if source is None or not self.backend.is_frame(source):
            raise ValueError(f"Collapse source dataset is unavailable: {source_id}")
        dimensions = self.resource_resolver.entity_dimensions(operation.entity_id)
        if not set(dimensions).issubset(operation.output_features):
            raise ValueError("Collapse output_features must include target entity dimensions")
        outputs = [output for output in operation.output_features if output not in dimensions]
        if not outputs:
            raise ValueError("Collapse must produce a non-dimension feature")
        kwargs = self._resolve_args(operation, dataset_frame=source)
        result = self.callable_loader.load(operation.entrypoint)(**kwargs)
        results = self._output_values(operation, result, outputs)
        expressions: list[object] = []
        for identifier in outputs:
            expression = results[identifier]
            if not self.backend.is_expression(expression):
                raise ValueError(
                    f"Collapse function {operation.function_id} must return "
                    f"an aggregation expression for {identifier}"
                )
            expressions.append(self.backend.alias(expression, identifier))
        result = self.backend.collapse(source, dimensions, expressions)
        self._runtime_fragments[(operation.entity_id, operation.output or operation.id)] = result
        self._runtime_datasets[(operation.entity_id, operation.dataset_id)] = self._merge_fragment(
            operation, result
        )

    def _merge_fragment(self, operation: Operation, fragment: object) -> object:
        """Validate and merge a fragment using its entity dimension keys."""
        if not self.backend.is_frame(fragment):
            raise ValueError(
                f"Fragment {operation.function_id} must return a Polars DataFrame or LazyFrame"
            )
        dimensions = self.resource_resolver.entity_dimensions(operation.entity_id)
        self._validate_fragment_keys(operation, fragment, dimensions)
        dataset_id = operation.dataset_id
        key = (operation.entity_id, dataset_id)
        existing = self._runtime_datasets.get(key)
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
        self, operation: Operation, fragment: object, dimensions: list[str]
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

    def _execute_vectorize(self, operation: Operation) -> None:
        """Run a vectorize mapping and append its output columns to the dataset."""
        dataset_key = (operation.entity_id, operation.dataset_id)
        kwargs = self._resolve_args(operation, dataset_key=dataset_key)
        result = self.callable_loader.load(operation.entrypoint)(**kwargs)
        outputs = operation.output_features or [operation.output or operation.function_id]
        results = self._output_values(operation, result, outputs)
        elements = [self._as_column(results[output], output) for output in outputs]
        self._runtime_datasets[dataset_key] = self.backend.with_columns(
            self._runtime_datasets[dataset_key], elements
        )
        for output, element in zip(outputs, elements, strict=True):
            self._runtime_calculations[(*dataset_key, output)] = element

    @staticmethod
    def _output_values(
        operation: Operation, result: object, outputs: list[str]
    ) -> Mapping[str, object]:
        """Validate a function's return value against its declared analytical outputs."""
        label = operation.kind.capitalize()
        if len(outputs) == 1:
            return {outputs[0]: result}
        if isinstance(result, Mapping):
            if not all(isinstance(name, str) for name in result):
                raise ValueError(
                    f"{label} mapping {operation.id} returned non-string output identifiers"
                )
            unknown = sorted(set(result) - set(outputs))
            missing = sorted(set(outputs) - set(result))
            if unknown or missing:
                details = []
                if missing:
                    details.append("missing outputs: " + ", ".join(missing))
                if unknown:
                    details.append("unexpected outputs: " + ", ".join(unknown))
                raise ValueError(
                    f"{label} mapping {operation.id} returned invalid outputs "
                    f"({'; '.join(details)})"
                )
            return result
        raise ValueError(
            f"{label} mapping {operation.id} must return a mapping of "
            "feature IDs to values when it produces multiple features"
        )

    def _execute_sink(self, operation: Operation) -> None:
        """Persist the selected columns of the accumulated dataset."""
        frame = self._runtime_datasets[(operation.entity_id, operation.dataset_id)]
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

    def _feature_value(
        self, feature: str, dataset_frame: object, dataset_key: tuple[str, str] | None
    ) -> object | None:
        calculation = (
            self._runtime_calculations.get((*dataset_key, feature))
            if dataset_key is not None
            else None
        )
        if calculation is not None:
            return calculation
        if dataset_frame is None:
            return self.backend.feature_column(feature)
        return (
            self.backend.feature_column(feature)
            if feature in self.backend.column_names(dataset_frame)
            else None
        )

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

    def _as_column(self, element: object, feature: str) -> object:
        """Return a calculation result as a named backend column."""
        if self.backend.is_column(element):
            return self.backend.alias(element, feature)
        return self.backend.alias(self.backend.literal(element), feature)
