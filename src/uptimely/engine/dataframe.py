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
        dataset = self._dataset(invocation.dataset_id)
        self.backend.validate_types(
            result,
            self._declared_types(dataset, [*dimensions, *invocation.output_features]),
        )
        if invocation.operation == operations.VECTORIZE:
            validate_coverage = (
                input_frame is not None
                and self.backend.should_validate_values(input_frame)
                and self.backend.should_validate_values(result)
            )
            if input_frame is None or (
                validate_coverage and not self.backend.same_keys(input_frame, result, dimensions)
            ):
                raise ValueError(
                    f"Vectorize mapping {invocation.mapping_id} must preserve "
                    "the dataset dimension keys"
                )

    def assemble_fragment(
        self,
        invocation: execution_plan.Invocation,
        result: object,
        existing: object | None,
        input_frame: object | None,
        dimensions: list[str],
    ) -> tuple[object, object]:
        """Validate a mapping result and assemble its declared fragment."""
        self.validate_result(invocation, result, input_frame, dimensions)
        fragment = self.backend.select(
            result, list(dict.fromkeys([*dimensions, *invocation.output_features]))
        )
        if existing is not None:
            dataset = self._dataset(invocation.dataset_id)
            self._validate_frame_keys(existing, dimensions, "Accumulated dataset")
            existing_columns = set(self.backend.column_names(existing))
            self.backend.validate_types(
                existing,
                self._declared_types(
                    dataset,
                    [
                        *dimensions,
                        *(name for name in dataset.features if name in existing_columns),
                    ],
                ),
            )
            self._validate_feature_collisions(existing, fragment, dimensions)
            merged = self._join_fragments(existing, fragment, dimensions)
        else:
            merged = fragment
        return fragment, merged

    def merge_fragment(
        self, existing: object | None, fragment: object, dimensions: list[str]
    ) -> object:
        """Join unique fragments on complete keys without replacing feature columns."""
        self._validate_frame_keys(fragment, dimensions, "Fragment")
        if existing is None:
            return fragment
        self._validate_frame_keys(existing, dimensions, "Accumulated dataset")
        self._validate_feature_collisions(existing, fragment, dimensions)
        return self._join_fragments(existing, fragment, dimensions)

    def _validate_feature_collisions(
        self, existing: object, fragment: object, dimensions: list[str]
    ) -> None:
        """Reject output feature names already present in the accumulated dataset."""
        existing_columns = set(self.backend.column_names(existing))
        fragment_columns = set(self.backend.column_names(fragment))
        collisions = sorted((fragment_columns - set(dimensions)) & existing_columns)
        if collisions:
            raise ValueError(
                "Fragment feature columns overlap the accumulated dataset: " + ", ".join(collisions)
            )

    def _join_fragments(self, existing: object, fragment: object, dimensions: list[str]) -> object:
        """Join validated frames, retaining the native eager/lazy behavior."""
        left = existing
        right = fragment
        if type(existing) is not type(fragment):
            left = self.backend.lazy(existing)
            right = self.backend.lazy(right)
        return self.backend.join(left, right, dimensions)

    def _dataset(self, dataset_id: str | None) -> spec_model.Dataset:
        """Return the spec definition for a project-wide dataset ID."""
        dataset = next(
            (
                dataset
                for entity in self.spec_definition.entities.values()
                if (dataset := entity.datasets.get(dataset_id)) is not None
            ),
            None,
        )
        if dataset is None:
            raise ValueError(f"Unknown dataset: {dataset_id}")
        return dataset

    def _declared_types(self, dataset: spec_model.Dataset, columns: list[str]) -> dict[str, str]:
        """Return logical types declared for the selected dataset columns."""
        types: dict[str, str] = {}
        for name in dict.fromkeys(columns):
            definition = self.spec_definition.dimensions.get(name) or dataset.features.get(name)
            if definition is not None and definition.type is not None:
                types[name] = definition.type
        return types

    def _validate_frame_keys(self, frame: object, dimensions: list[str], description: str) -> None:
        """Require complete unique keys, or at most one dimensionless row."""
        if not self.backend.is_frame(frame):
            raise ValueError(f"{description} must be a Polars DataFrame or LazyFrame")
        columns = set(self.backend.column_names(frame))
        missing = sorted(set(dimensions) - columns)
        if missing:
            raise ValueError(f"{description} is missing dimension columns: " + ", ".join(missing))
        if not self.backend.should_validate_values(frame):
            return
        if not dimensions:
            if self.backend.row_count(frame) > 1:
                raise ValueError(
                    f"{description} contains duplicate dimension keys "
                    "(dimensionless datasets allow at most one row)"
                )
            return
        keys = self.backend.select(frame, dimensions)
        if self.backend.is_duplicated(keys):
            raise ValueError(f"{description} contains duplicate dimension keys")

    def validate_fragment_keys(
        self, invocation: execution_plan.Invocation, fragment: object, dimensions: list[str]
    ) -> None:
        """Validate the dimension-key contract of one dataframe fragment."""
        self._validate_frame_keys(fragment, dimensions, f"Fragment {invocation.function_id}")
