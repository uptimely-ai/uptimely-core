"""Invoke plan operations and publish their results to materialized datasets."""

import collections
import functools
import logging
import typing

from uptimely import entrypoint as entrypoint_module
from uptimely import plan as plan_module
from uptimely.engine.dataframe import backend as backend_module
from uptimely.engine.dataframe import dataset as dataset_module
from uptimely.engine.dataframe import fragment as fragment_module
from uptimely.spec import arg_types, function_kinds

from . import bindings as bindings_module
from . import state as state_module

logger = logging.getLogger(__name__)


class InvocationExecutor:
    """Dispatch invocations and publish results into per-profile datasets."""

    def __init__(
        self,
        backend: backend_module.DataFrameBackend,
        entrypoints: typing.Mapping[str, entrypoint_module.Entrypoint],
        parameters: typing.Mapping[str, typing.Any],
        state: state_module.RuntimeState,
        *,
        validate: bool = False,
    ) -> None:
        """Create an executor with optional runtime contract validation."""
        self.backend = backend
        self.entrypoints = entrypoints
        self.state = state
        self.validate = validate
        self.bindings = bindings_module.RuntimeBindings(state, parameters)

    def execute(self, invocation: plan_module.Invocation) -> None:
        """Execute one invocation, validating before side effects and state updates."""
        definition = function_kinds.FUNCTION_KINDS.get(invocation.function_kind)
        if definition is None:
            raise ValueError(f"Unsupported invocation function kind: {invocation.function_kind}")
        if invocation.function_kind == function_kinds.MERGE:
            self._execute_merge(invocation)
            return
        if definition.is_effect:
            self._invoke(invocation)
            return
        if self.validate:
            self.check_input_requirements(invocation)
        if definition.returns == arg_types.DATAFRAME:
            if definition.produces_fragment:
                self._execute_dataframe_operator(invocation)
            else:
                self._execute_column_operator(invocation)
        else:
            if invocation.dataset_id not in self.state.main_frames:
                raise KeyError(invocation.dataset_id)
            self._invoke(invocation)

    def check_input_requirements(self, invocation: plan_module.Invocation) -> None:
        """Check input scope and feature availability before execution.

        Raises:
            ValueError: A source reference is invalid or required features are
                unavailable or ambiguous.
        """
        logger.debug("  Requirements:")
        definition = function_kinds.FUNCTION_KINDS[invocation.function_kind]
        if definition.dataframe_input_scope == "foreign":
            argument_name = self._check_foreign_dataframe_argument(invocation)
            source_id = self._check_foreign_source_reference(invocation, argument_name)
            source = self._check_foreign_source_available(source_id)
            self._check_foreign_input_features(invocation, source)
        else:
            self._check_input_features(invocation)

    def _check_input_features(self, invocation: plan_module.Invocation) -> None:
        """Require each feature locally or in exactly one other profile."""
        logger.debug("    - checking declared input features")
        target = self.state.main_frames.get(invocation.dataset_id)
        target_columns = (
            set(self.backend.column_names(target.dataframe)) if target is not None else set()
        )
        required = set(invocation.input_features) - target_columns
        if not required:
            return
        available = collections.Counter(
            column
            for dataset_id, frame in self.state.main_frames.items()
            if dataset_id != invocation.dataset_id
            for column in set(self.backend.column_names(frame.dataframe))
        )
        for feature in invocation.input_features:
            if feature in required and available[feature] != 1:
                raise ValueError(
                    f"Operator {invocation.operator_id} input feature is unavailable or ambiguous: "
                    f"{feature}"
                )

    @staticmethod
    def _dataframe_arguments(invocation: plan_module.Invocation) -> list[str]:
        """Return names of declared dataframe arguments."""
        return [
            name
            for name, argument_type in invocation.argument_types.items()
            if argument_type == arg_types.DATAFRAME
        ]

    def _check_foreign_dataframe_argument(self, invocation: plan_module.Invocation) -> str:
        """Require and return the single dataframe argument for a foreign input."""
        logger.debug("    - checking foreign dataframe argument")
        arguments = self._dataframe_arguments(invocation)
        if len(arguments) != 1:
            raise ValueError(
                f"Operator {invocation.operator_id} must declare exactly one foreign "
                "dataframe argument"
            )
        return arguments[0]

    def _check_foreign_source_reference(
        self, invocation: plan_module.Invocation, argument_name: str
    ) -> str:
        """Require a dataset reference distinct from the invocation's target."""
        logger.debug("    - checking foreign source reference")
        source_id = invocation.arguments.get(argument_name)
        if not isinstance(source_id, str) or source_id == invocation.dataset_id:
            raise ValueError(
                f"Operator {invocation.operator_id} must reference a foreign source profile"
            )
        return source_id

    def _check_foreign_source_available(self, source_id: str) -> dataset_module.Dataset:
        """Require the referenced source profile to be available."""
        logger.debug("    - checking foreign source availability")
        source = self.state.main_frames.get(source_id)
        if source is None:
            raise ValueError(f"Profile dataframe is unavailable: {source_id}")
        return source

    def _check_foreign_input_features(
        self, invocation: plan_module.Invocation, source: dataset_module.Dataset
    ) -> None:
        """Require declared features in the validated foreign source."""
        logger.debug("    - checking foreign input features")
        columns = set(self.backend.column_names(source.dataframe))
        for feature in invocation.input_features:
            if feature not in columns:
                raise ValueError(
                    f"Operator {invocation.operator_id} input feature is unavailable in foreign "
                    f"source profile: {feature}"
                )

    def _execute_dataframe_operator(self, invocation: plan_module.Invocation) -> None:
        """Produce and retain a fragment for its scheduled merge invocation."""
        dataset_id = self._profile_id(invocation)
        dataset = self.state.main_frames.get(dataset_id)
        fragment = fragment_module.Fragment.stage(
            self.backend,
            invocation,
            functools.partial(self._invoke, invocation),
            validate=self.validate,
            comparison_frame=dataset.dataframe if dataset is not None else None,
        )
        self.state.staged_fragments[invocation.id] = fragment

    def _execute_merge(self, invocation: plan_module.Invocation) -> None:
        """Invoke a merge binding and publish its complete target frame on success."""
        dataset_id = self._profile_id(invocation)
        fragment_id, fragment = self.state.staged_fragment_for(invocation)
        current = self.state.main_frames.get(dataset_id)
        target = current.dataframe if current is not None else None
        logger.debug("  Merge:\n    Target profile: %s", dataset_id)
        arguments = self.bindings.resolve_args(invocation, staged_fragment=fragment.dataframe)
        if current is not None:
            current.validate_fragment_merge(
                fragment,
                description="Accumulated profile",
                column_types=invocation.column_types,
                validate=self.validate,
            )

        result = self._invoke(invocation, arguments=arguments)
        candidate = dataset_module.Dataset(
            self.backend,
            invocation.id_columns,
            result,
        )
        candidate.validate_merge_candidate(
            target,
            fragment,
            description=f"Merge result {invocation.function_id}",
            column_types=invocation.column_types,
            validate=self.validate,
        )

        if current is None:
            dataset = candidate
        else:
            current.dataframe = result
            dataset = current
        dataset.fragments[fragment.invocation.operator_id] = fragment
        self.state.main_frames[dataset_id] = dataset
        del self.state.staged_fragments[fragment_id]

    def _execute_column_operator(self, invocation: plan_module.Invocation) -> None:
        """Publish vectorized columns on the target frame without fragment assembly."""
        dataset_id = self._profile_id(invocation)
        dataset = self.state.main_frames.get(dataset_id)
        if dataset is None or dataset.dataframe is None:
            raise ValueError(f"Profile dataframe is unavailable: {dataset_id}")
        comparison_frame = dataset.dataframe
        if self.validate:
            comparison_frame = self.backend.snapshot(comparison_frame)
            arguments = self.bindings.resolve_args(invocation)
            for name, argument_type in invocation.argument_types.items():
                if (
                    argument_type == arg_types.DATAFRAME
                    and invocation.arguments.get(name) == dataset_id
                ):
                    arguments[name] = comparison_frame
            frame = self._invoke(invocation, arguments=arguments)
        else:
            frame = self._invoke(invocation)
        output_features = self._validate_vectorized_result(
            frame,
            invocation,
            comparison_frame,
            preserve_data=self.validate,
        )
        calculated_outputs = {
            (dataset_id, output): self.backend.select(frame, [*invocation.id_columns, output])
            for output in output_features
        }
        dataset.dataframe = frame
        self.state.calculated_outputs.update(calculated_outputs)

    def _validate_vectorized_result(
        self,
        frame: object,
        invocation: plan_module.Invocation,
        comparison_frame: object,
        *,
        preserve_data: bool,
    ) -> list[str]:
        """Validate an invocation's vectorized result against its target frame.

        Args:
            frame: Candidate dataframe returned by the invocation.
            invocation: Invocation whose output and preservation contracts apply.
            comparison_frame: Original target used for collision and preservation checks.
            preserve_data: Whether to compare existing values, row order, and types.

        Returns:
            Declared output feature names, excluding identifier columns.

        Raises:
            ValueError: The result violates the vectorized dataframe contract.
        """
        description = f"Vectorize result {invocation.function_id}"
        logger.debug("  Enriched target frame:")
        logger.debug("    - checking dataframe type")
        if not self.backend.is_frame(frame):
            raise ValueError(f"{description} must be a Polars DataFrame or LazyFrame")
        logger.debug("    - checking required dimension columns")
        frame_columns = set(self.backend.column_names(frame))
        missing_dimensions = sorted(set(invocation.id_columns) - frame_columns)
        if missing_dimensions:
            raise ValueError(
                f"{description} is missing dimension columns: " + ", ".join(missing_dimensions)
            )

        output_features = [
            output for output in invocation.output_features if output not in invocation.id_columns
        ]
        logger.debug("    - checking declared vectorize outputs")
        missing_outputs = sorted(set(output_features) - frame_columns)
        if missing_outputs:
            raise ValueError(
                f"Vectorize operator {invocation.operator_id} is missing output columns: "
                + ", ".join(missing_outputs)
            )

        logger.debug("    - checking vectorize output collisions")
        existing_columns = set(self.backend.column_names(comparison_frame))
        existing_features = existing_columns - set(invocation.id_columns)
        collisions = sorted(set(output_features) & existing_features)
        if collisions:
            raise ValueError(
                f"Vectorize operator {invocation.operator_id} cannot replace existing "
                "columns: " + ", ".join(collisions)
            )

        logger.debug("    - checking preservation of existing columns")
        missing_existing = sorted(existing_columns - frame_columns)
        if missing_existing:
            raise ValueError(
                f"Vectorize operator {invocation.operator_id} must preserve existing "
                "columns: " + ", ".join(missing_existing)
            )

        logger.debug("    - checking undeclared added columns")
        allowed_columns = existing_columns | set(output_features)
        unexpected = sorted(frame_columns - allowed_columns)
        if unexpected:
            raise ValueError(
                f"Vectorize operator {invocation.operator_id} returned undeclared columns: "
                + ", ".join(unexpected)
            )

        if preserve_data:
            definition = function_kinds.FUNCTION_KINDS[invocation.function_kind]
            if (
                definition.row_order_relation == "preserve"
                or definition.existing_data_relation == "preserve"
            ):
                logger.debug("    - checking existing values and row order")
                existing_names = self.backend.column_names(comparison_frame)
                if not self.backend.same_data(comparison_frame, frame, existing_names):
                    raise ValueError(
                        f"Vectorize operator {invocation.operator_id} must preserve existing "
                        "column values and row order"
                    )
            logger.debug("    - checking types of target keys and outputs")
            column_types = {
                name: invocation.column_types[name]
                for name in [*invocation.id_columns, *output_features]
                if name in invocation.column_types
            }
            logger.debug("      Declared types: %s", column_types)
            self.backend.validate_types(frame, column_types)
        return output_features

    @staticmethod
    def _profile_id(invocation: plan_module.Invocation) -> str:
        """Require a target profile ID for a dataframe invocation."""
        if invocation.dataset_id is None:
            raise ValueError(f"Dataframe invocation {invocation.id} must declare a profile ID")
        return invocation.dataset_id

    def _invoke(
        self,
        invocation: plan_module.Invocation,
        *,
        arguments: typing.Mapping[str, object] | None = None,
    ) -> object:
        """Resolve arguments and invoke the entrypoint for one plan invocation."""
        kwargs = self.bindings.resolve_args(invocation) if arguments is None else arguments
        entrypoint = self.entrypoints.get(invocation.entrypoint)
        if entrypoint is None:
            entrypoint = entrypoint_module.Entrypoint(invocation.entrypoint)
        return entrypoint.load()(**kwargs)
