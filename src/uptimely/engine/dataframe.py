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
        dataframe = self.state.datasets.get(invocation.dataset_id)
        dataframe_columns = (
            set(self.backend.column_names(dataframe)) if dataframe is not None else set()
        )
        required = set(invocation.input_features) - dataframe_columns
        if not required:
            return
        available = [
            set(self.backend.column_names(candidate_dataframe))
            for dataset_id, candidate_dataframe in self.state.datasets.items()
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

    def _validate_fragment(
        self,
        invocation: execution_plan.Invocation,
        fragment: object,
        dataframe: object | None,
        dimensions: list[str],
    ) -> None:
        """Check fragment keys, declared outputs, and logical types."""
        self._validate_dataframe(
            fragment,
            dimensions,
            f"Fragment {invocation.function_id}",
            invalid_frame_message=(
                f"Fragment {invocation.function_id} must return a Polars DataFrame or LazyFrame"
            ),
        )
        columns = set(self.backend.column_names(fragment))
        missing = sorted(set(invocation.output_features) - columns)
        if missing:
            raise ValueError(
                f"Mapping {invocation.mapping_id} is missing output columns: " + ", ".join(missing)
            )
        dataset = self._dataset(invocation.dataset_id)
        self._validate_declared_types(
            fragment,
            dataset,
            [*dimensions, *invocation.output_features],
        )
        if invocation.operation == operations.VECTORIZE:
            validate_coverage = (
                dataframe is not None
                and self.backend.should_validate_values(dataframe)
                and self.backend.should_validate_values(fragment)
            )
            if dataframe is None or (
                validate_coverage and not self.backend.same_keys(dataframe, fragment, dimensions)
            ):
                raise ValueError(
                    f"Vectorize mapping {invocation.mapping_id} must preserve "
                    "the dataset dimension keys"
                )

    def assemble_fragment(
        self,
        invocation: execution_plan.Invocation,
        fragment: object,
        dataframe: object | None,
        dimensions: list[str],
    ) -> tuple[object, object]:
        """Validate a mapping result and assemble its declared fragment."""
        self._validate_fragment(invocation, fragment, dataframe, dimensions)
        fragment = self.backend.select(
            fragment, list(dict.fromkeys([*dimensions, *invocation.output_features]))
        )
        if dataframe is not None:
            dataset = self._dataset(invocation.dataset_id)
            self._validate_dataframe(dataframe, dimensions, "Accumulated dataset")
            dataframe_columns = set(self.backend.column_names(dataframe))
            self._validate_declared_types(
                dataframe,
                dataset,
                [
                    *dimensions,
                    *(name for name in dataset.features if name in dataframe_columns),
                ],
            )
        return fragment, self._combine_fragment(dataframe, fragment, dimensions)

    def merge_fragment(
        self, dataframe: object | None, fragment: object, dimensions: list[str]
    ) -> object:
        """Join unique fragments on complete keys without replacing feature columns."""
        self._validate_dataframe(fragment, dimensions, "Fragment")
        if dataframe is not None:
            self._validate_dataframe(dataframe, dimensions, "Accumulated dataset")
        return self._combine_fragment(dataframe, fragment, dimensions)

    def _combine_fragment(
        self, dataframe: object | None, fragment: object, dimensions: list[str]
    ) -> object:
        """Combine a validated fragment with the accumulated dataframe."""
        if dataframe is None:
            return fragment
        self._validate_feature_collisions(dataframe, fragment, dimensions)
        return self._join_fragments(dataframe, fragment, dimensions)

    def _validate_feature_collisions(
        self, dataframe: object, fragment: object, dimensions: list[str]
    ) -> None:
        """Reject output feature names already present in the accumulated dataset."""
        dataframe_columns = set(self.backend.column_names(dataframe))
        fragment_columns = set(self.backend.column_names(fragment))
        collisions = sorted((fragment_columns - set(dimensions)) & dataframe_columns)
        if collisions:
            raise ValueError(
                "Fragment feature columns overlap the accumulated dataset: " + ", ".join(collisions)
            )

    def _join_fragments(self, dataframe: object, fragment: object, dimensions: list[str]) -> object:
        """Join validated frames, retaining the native eager/lazy behavior."""
        left = dataframe
        right = fragment
        if type(dataframe) is not type(fragment):
            left = self.backend.lazy(dataframe)
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

    def _validate_declared_types(
        self, dataframe: object, dataset: spec_model.Dataset, columns: list[str]
    ) -> None:
        """Validate dataframe columns against their declared logical types."""
        self.backend.validate_types(dataframe, self._declared_types(dataset, columns))

    def _validate_dataframe(
        self,
        dataframe: object,
        dimensions: list[str],
        description: str,
        invalid_frame_message: str | None = None,
    ) -> None:
        """Validate dataframe type and dimension-key integrity."""
        if not self.backend.is_frame(dataframe):
            raise ValueError(
                invalid_frame_message or f"{description} must be a Polars DataFrame or LazyFrame"
            )
        columns = set(self.backend.column_names(dataframe))
        missing = sorted(set(dimensions) - columns)
        if missing:
            raise ValueError(f"{description} is missing dimension columns: " + ", ".join(missing))
        if self.backend.should_validate_values(dataframe):
            if not dimensions:
                if self.backend.row_count(dataframe) > 1:
                    raise ValueError(
                        f"{description} contains duplicate dimension keys "
                        "(dimensionless datasets allow at most one row)"
                    )
            else:
                keys = self.backend.select(dataframe, dimensions)
                if self.backend.is_duplicated(keys):
                    raise ValueError(f"{description} contains duplicate dimension keys")
