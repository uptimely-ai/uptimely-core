"""Dataframe execution contracts for portable plan invocations."""

from uptimely import execution_plan
from uptimely.spec import functions
from uptimely.spec import model as spec_model

from . import backend as backend_module
from . import dataframe_validation as dataframe_validation_module
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
        dataframe_validation_module.validate_dataframes(
            dataframe_validation_module.InputValidationContext(
                self.backend,
                self.spec_definition,
                self.state,
                invocation,
            ),
            (
                dataframe_validation_module.validate_input_function,
                dataframe_validation_module.validate_input_features,
            ),
        )

    def _validate_fragment(
        self,
        invocation: execution_plan.Invocation,
        fragment: object,
        dataframe: object | None,
        dimensions: list[str],
        output_features: list[str] | None = None,
    ) -> None:
        """Check fragment keys, declared outputs, and logical types."""
        dataframe_validation_module.validate_dataframes(
            dataframe_validation_module.FrameValidationContext(
                self.backend,
                self.spec_definition,
                fragment,
                dimensions,
                f"Fragment {invocation.function_id}",
                invalid_frame_message=(
                    f"Fragment {invocation.function_id} must return a Polars DataFrame or LazyFrame"
                ),
                invocation=invocation,
                output_features=output_features,
                dataset=self._dataset(invocation.dataset_id),
                comparison_frame=dataframe,
            ),
            (
                dataframe_validation_module.validate_frame_type,
                dataframe_validation_module.validate_dimension_columns,
                dataframe_validation_module.validate_unique_dimension_keys,
                dataframe_validation_module.validate_output_columns,
                dataframe_validation_module.validate_fragment_declared_types,
                dataframe_validation_module.validate_key_coverage,
            ),
        )

    def assemble_fragment(
        self,
        invocation: execution_plan.Invocation,
        fragment: object,
        dataframe: object | None,
        dimensions: list[str],
    ) -> tuple[object, object]:
        """Validate an action result and assemble its declared fragment."""
        dataset = self._dataset(invocation.dataset_id)
        output_features = [
            feature for feature in invocation.output_features if feature not in dimensions
        ]
        if not output_features:
            return fragment, dataframe

        fragment_dimensions = dimensions
        if invocation.function_kind == functions.EXPAND and self.backend.is_frame(fragment):
            fragment_dimensions = self._carried_dimensions(fragment, dimensions)
        self._validate_fragment(
            invocation, fragment, dataframe, fragment_dimensions, output_features=output_features
        )
        fragment = self.backend.select(
            fragment, list(dict.fromkeys([*fragment_dimensions, *output_features]))
        )
        if dataframe is not None:
            self._validate_dataframe(dataframe, dimensions, "Accumulated dataset")
            dataframe_columns = set(self.backend.column_names(dataframe))
            dataframe_validation_module.validate_dataframes(
                dataframe_validation_module.FrameValidationContext(
                    self.backend,
                    self.spec_definition,
                    dataframe,
                    dimensions,
                    "Accumulated dataset",
                    dataset=dataset,
                    declared_type_columns=[
                        *dimensions,
                        *(name for name in dataset.features if name in dataframe_columns),
                    ],
                ),
                (dataframe_validation_module.validate_dataset_declared_types,),
            )
        if fragment_dimensions != dimensions:
            return fragment, self._broadcast_fragment(
                invocation, dataframe, fragment, fragment_dimensions
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

    def _carried_dimensions(self, fragment: object, dimensions: list[str]) -> list[str]:
        """Return the target dimension keys carried by an expand fragment."""
        columns = set(self.backend.column_names(fragment))
        return [dimension for dimension in dimensions if dimension in columns]

    def _broadcast_fragment(
        self,
        invocation: execution_plan.Invocation,
        dataframe: object | None,
        fragment: object,
        fragment_dimensions: list[str],
    ) -> object:
        """Left-join an expand fragment onto the accumulated dataset by its carried keys."""
        if dataframe is None:
            raise ValueError(
                f"Expand action {invocation.mapping_id} fragment carries a subset of the "
                "dimension keys and requires the accumulated target dataset"
            )
        self._validate_feature_collisions(dataframe, fragment, fragment_dimensions)
        left, right = self._aligned_frames(dataframe, fragment)
        return self.backend.left_join(left, right, fragment_dimensions)

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
        left, right = self._aligned_frames(dataframe, fragment)
        return self.backend.join(left, right, dimensions)

    def _aligned_frames(self, dataframe: object, fragment: object) -> tuple[object, object]:
        """Return both frames, made lazy together when their types differ."""
        if type(dataframe) is not type(fragment):
            return self.backend.lazy(dataframe), self.backend.lazy(fragment)
        return dataframe, fragment

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

    def _validate_dataframe(
        self,
        dataframe: object,
        dimensions: list[str],
        description: str,
        invalid_frame_message: str | None = None,
    ) -> None:
        """Validate dataframe type and dimension-key integrity."""
        dataframe_validation_module.validate_dataframes(
            dataframe_validation_module.FrameValidationContext(
                self.backend,
                self.spec_definition,
                dataframe,
                dimensions,
                description,
                invalid_frame_message,
            ),
            (
                dataframe_validation_module.validate_frame_type,
                dataframe_validation_module.validate_dimension_columns,
                dataframe_validation_module.validate_unique_dimension_keys,
            ),
        )
