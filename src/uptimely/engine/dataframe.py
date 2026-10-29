"""Dataframe execution contracts for portable plan invocations."""

from uptimely import execution_plan
from uptimely.spec import arg_types, functions
from uptimely.spec import model as spec_model

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
        if invocation.function_kind in {
            functions.CONFORM,
            functions.COLLAPSE,
            functions.EXPAND,
        }:
            self._validate_foreign_inputs(invocation)
            return

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
                    f"Action {invocation.mapping_id} input feature is unavailable or ambiguous: "
                    f"{feature}"
                )

    def _validate_foreign_inputs(self, invocation: execution_plan.Invocation) -> None:
        """Check dimensional inputs against the operation's foreign dataframe."""
        function = self.spec_definition.functions.get(invocation.function_id)
        if function is None:
            raise ValueError(f"Unknown function: {invocation.function_id}")
        dataframe_arguments = [
            name for name, argument in function.args.items() if argument.type == arg_types.DATAFRAME
        ]
        if len(dataframe_arguments) != 1:
            raise ValueError(
                f"Action {invocation.mapping_id} must declare exactly one foreign dataframe "
                "argument"
            )
        argument_name = dataframe_arguments[0]
        source_id = invocation.arguments.get(argument_name)
        if not isinstance(source_id, str) or source_id == invocation.dataset_id:
            raise ValueError(
                f"Action {invocation.mapping_id} must reference a foreign source dataset"
            )
        source = self.state.datasets.get(source_id)
        if source is None:
            raise ValueError(f"Dataset dataframe is unavailable: {source_id}")

        source_columns = set(self.backend.column_names(source))
        for feature in invocation.input_features:
            if feature not in source_columns:
                raise ValueError(
                    f"Action {invocation.mapping_id} input feature is unavailable in foreign "
                    f"source dataset: {feature}"
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
        output_features = output_features or invocation.output_features
        self._validate_dataframe(
            fragment,
            dimensions,
            f"Fragment {invocation.function_id}",
            invalid_frame_message=(
                f"Fragment {invocation.function_id} must return a Polars DataFrame or LazyFrame"
            ),
        )
        columns = set(self.backend.column_names(fragment))
        missing = sorted(set(output_features) - columns)
        if missing:
            raise ValueError(
                f"Action {invocation.mapping_id} is missing output columns: " + ", ".join(missing)
            )
        dataset = self._dataset(invocation.dataset_id)
        self._validate_declared_types(
            fragment,
            dataset,
            [*dimensions, *output_features],
        )
        if invocation.function_kind == functions.VECTORIZE:
            validate_coverage = (
                dataframe is not None
                and self.backend.should_validate_values(dataframe)
                and self.backend.should_validate_values(fragment)
            )
            if dataframe is None or (
                validate_coverage and not self.backend.same_keys(dataframe, fragment, dimensions)
            ):
                raise ValueError(
                    f"Vectorize action {invocation.mapping_id} must preserve "
                    "the dataset dimension keys"
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
            self._validate_declared_types(
                dataframe,
                dataset,
                [
                    *dimensions,
                    *(name for name in dataset.features if name in dataframe_columns),
                ],
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
