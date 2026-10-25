"""Dataframe execution contracts for portable plan invocations."""

from uptimely import execution_plan
from uptimely.spec import model as spec_model
from uptimely.spec import operations

from . import backend as backend_module
from . import state as state_module


class DataFrameExecution:
    """Validate and combine dataframe values using the configured backend."""

    def __init__(
        self,
        backend: backend_module.DataFrameBackend,
        spec_definition: spec_model.Spec,
        state: state_module.RuntimeState,
    ) -> None:
        """Create dataframe operations bound to one backend and execution state."""
        self.backend = backend
        self.spec_definition = spec_definition
        self.state = state

    def validate_inputs(self, invocation: execution_plan.Invocation) -> None:
        """Require declared input columns to be materialized before invocation."""
        current = self.state.datasets.get(invocation.dataset_id)
        current_columns = set(self.backend.column_names(current)) if current is not None else set()
        required = set(invocation.input_features) - current_columns
        if not required:
            return
        available = [
            set(self.backend.column_names(frame))
            for dataset_id, frame in self.state.datasets.items()
            if dataset_id != invocation.dataset_id
        ]
        for feature in invocation.input_features:
            if feature not in required:
                continue
            if sum(feature in columns for columns in available) != 1:
                raise ValueError(
                    f"Mapping {invocation.mapping_id} input feature is unavailable or ambiguous: "
                    f"{feature}"
                )

    def validate_result(
        self,
        invocation: execution_plan.Invocation,
        result: object,
        input_frame: object,
        dimensions: list[str],
    ) -> None:
        """Check returned frame keys, declared outputs, and logical types."""
        if not self.backend.is_frame(result):
            raise ValueError(
                f"Fragment {invocation.function_id} must return a Polars DataFrame or LazyFrame"
            )
        self.validate_fragment_keys(invocation, result, dimensions)
        columns = set(self.backend.column_names(result))
        missing = sorted(set(invocation.output_features) - columns)
        if missing:
            raise ValueError(
                f"Mapping {invocation.mapping_id} is missing output columns: " + ", ".join(missing)
            )
        dataset = next(
            (
                dataset
                for entity in self.spec_definition.entities.values()
                if (dataset := entity.datasets.get(invocation.dataset_id)) is not None
            ),
            None,
        )
        if dataset is None:
            raise ValueError(f"Unknown dataset: {invocation.dataset_id}")
        types: dict[str, str] = {}
        for name in dict.fromkeys([*dimensions, *invocation.output_features]):
            definition = (
                self.spec_definition.dimensions.get(name)
                if name in dimensions
                else dataset.features.get(name)
            )
            column_type = definition.type if definition is not None else None
            if column_type is not None:
                types[name] = column_type
        self.backend.validate_types(result, types)
        if invocation.operation == operations.VECTORIZE and (
            input_frame is None or not self.backend.same_keys(input_frame, result, dimensions)
        ):
            raise ValueError(
                f"Vectorize mapping {invocation.mapping_id} must preserve the dataset dimension "
                "keys"
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
        self, invocation: execution_plan.Invocation, fragment: object, dimensions: list[str]
    ) -> None:
        """Validate the dimension-key contract of one dataframe fragment."""
        columns = set(self.backend.column_names(fragment))
        missing = sorted(set(dimensions) - columns)
        if missing:
            raise ValueError(
                f"Fragment {invocation.function_id} is missing dimension columns: "
                + ", ".join(missing)
            )
        if not dimensions:
            if self.backend.row_count(fragment) > 1:
                raise ValueError(
                    f"Fragment {invocation.function_id} contains duplicate dimension keys "
                    "(dimensionless datasets allow at most one row)"
                )
            return
        keys = self.backend.select(fragment, dimensions)
        if not isinstance(keys, type(fragment)):
            keys = self.backend.collect(keys)
        if self.backend.is_duplicated(keys):
            raise ValueError(f"Fragment {invocation.function_id} contains duplicate dimension keys")
