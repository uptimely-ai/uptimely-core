"""Dataframe execution contracts for portable plan callables."""

import typing

from uptimely.compiler import plan as plan_module

from . import backend as backend_module
from . import state as state_module


class DataFrameExecution:
    """Validate and combine dataframe values using the configured backend."""

    def __init__(
        self,
        backend: backend_module.DataFrameBackend,
        resources: typing.Mapping[str, typing.Any],
        state: state_module.RuntimeState,
    ) -> None:
        """Create dataframe operations bound to one backend and execution state."""
        self.backend = backend
        self.resources = resources
        self.state = state

    def validate_inputs(self, callable: plan_module.Callable) -> None:
        """Require declared input columns to be materialized before invocation."""
        for feature in callable.input_features:
            frames = [
                frame
                for frame in self.state.datasets.values()
                if feature in self.backend.column_names(frame)
            ]
            current = self.state.datasets.get((callable.entity_id, callable.dataset_id))
            if current is not None and feature in self.backend.column_names(current):
                continue
            if len(frames) != 1:
                raise ValueError(
                    f"Mapping {callable.id} input feature is unavailable or ambiguous: {feature}"
                )

    def validate_result(
        self,
        callable: plan_module.Callable,
        result: object,
        input_frame: object,
        dimensions: list[str],
    ) -> None:
        """Check returned frame keys, declared outputs, and logical types."""
        if not self.backend.is_frame(result):
            raise ValueError(
                f"Fragment {callable.function_id} must return a Polars DataFrame or LazyFrame"
            )
        self.validate_fragment_keys(callable, result, dimensions)
        columns = set(self.backend.column_names(result))
        missing = sorted(set(callable.output_features) - columns)
        if missing:
            raise ValueError(
                f"Mapping {callable.id} is missing output columns: " + ", ".join(missing)
            )
        dimension_definitions = self.resources.get("dimensions", {})
        feature_definitions = (
            self.resources.get("datasets", {}).get(callable.dataset_id, {}).get("features", {})
        )
        types: dict[str, str] = {}
        for name in dict.fromkeys([*dimensions, *callable.output_features]):
            definitions = dimension_definitions if name in dimensions else feature_definitions
            column_type = definitions.get(name, {}).get("type")
            if column_type is not None:
                types[name] = column_type
        self.backend.validate_types(result, types)
        if callable.operation == "vectorize" and (
            input_frame is None or not self.backend.same_keys(input_frame, result, dimensions)
        ):
            raise ValueError(
                f"Vectorize mapping {callable.id} must preserve the dataset dimension keys"
            )

    def merge_fragment(self, existing: object, fragment: object, dimensions: list[str]) -> object:
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

    def validate_fragment_keys(
        self, callable: plan_module.Callable, fragment: object, dimensions: list[str]
    ) -> None:
        """Validate the dimension-key contract of one dataframe fragment."""
        columns = set(self.backend.column_names(fragment))
        missing = sorted(set(dimensions) - columns)
        if missing:
            raise ValueError(
                f"Fragment {callable.function_id} is missing dimension columns: "
                + ", ".join(missing)
            )
        if not dimensions:
            if self.backend.row_count(fragment) > 1:
                raise ValueError(
                    f"Fragment {callable.function_id} contains duplicate dimension keys "
                    "(dimensionless datasets allow at most one row)"
                )
            return
        keys = self.backend.select(fragment, dimensions)
        if not isinstance(keys, type(fragment)):
            keys = self.backend.collect(keys)
        if self.backend.is_duplicated(keys):
            raise ValueError(f"Fragment {callable.function_id} contains duplicate dimension keys")
