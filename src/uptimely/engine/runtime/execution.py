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
from uptimely.engine.dataframe import merge as merge_module
from uptimely.spec import arg_types

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
        if invocation.role == "merge":
            self._execute_merge(invocation)
            return
        if self.validate and (invocation.result != "none" or invocation.is_sink):
            self.check_input_requirements(invocation)
        if invocation.result == "none":
            self._invoke(invocation)
            return
        if invocation.result == "fragment":
            self._execute_dataframe_operator(invocation)
        elif invocation.result == "target":
            if invocation.dataframe_input_scope == "target":
                self._execute_column_operator(invocation)
            else:
                self._execute_target_operator(invocation)

    def check_input_requirements(self, invocation: plan_module.Invocation) -> None:
        """Check input scope and feature availability before execution.

        Raises:
            ValueError: A source reference is invalid or required features are
                unavailable or ambiguous.
        """
        if invocation.dataframe_input_scope == "foreign":
            argument_name = self._check_foreign_dataframe_argument(invocation)
            source_id = self._check_foreign_source_reference(invocation, argument_name)
            source = self._check_foreign_source_available(source_id)
            self._check_foreign_input_features(invocation, source)
        else:
            self._check_input_features(invocation)

    def _check_input_features(self, invocation: plan_module.Invocation) -> None:
        """Require each feature locally or in exactly one other profile."""
        logger.debug("Check declared input features")
        target = self.state.datasets.get(invocation.profile_id)
        target_columns = (
            set(self.backend.column_names(target.dataframe)) if target is not None else set()
        )
        required = set(invocation.input_features) - target_columns
        if not required:
            return
        available = collections.Counter(
            column
            for dataset_id, frame in self.state.datasets.items()
            if dataset_id != invocation.profile_id
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
        logger.debug("Check foreign dataframe argument")
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
        logger.debug("Check foreign source reference")
        source_id = invocation.arguments.get(argument_name)
        if not isinstance(source_id, str) or source_id == invocation.profile_id:
            raise ValueError(
                f"Operator {invocation.operator_id} must reference a foreign source profile"
            )
        return source_id

    def _check_foreign_source_available(self, source_id: str) -> dataset_module.Dataset:
        """Require the referenced source profile to be available."""
        logger.debug("Check foreign source availability")
        source = self.state.datasets.get(source_id)
        if source is None:
            raise ValueError(f"Profile dataframe is unavailable: {source_id}")
        return source

    def _check_foreign_input_features(
        self, invocation: plan_module.Invocation, source: dataset_module.Dataset
    ) -> None:
        """Require declared features in the validated foreign source."""
        logger.debug("Check foreign input features")
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
        dataset = self.state.datasets.get(dataset_id)
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
        current = self.state.datasets.get(dataset_id)
        dataset = (
            current
            if current is not None
            else dataset_module.Dataset(
                self.backend,
                invocation.target_identifiers,
                relations=[
                    column
                    for column in invocation.fragment_keys
                    if column not in invocation.target_identifiers
                ],
            )
        )
        logger.debug("Merging into profile %s", dataset_id)
        arguments = self.bindings.resolve_args(invocation, staged_fragment=fragment.dataframe)
        if invocation.entrypoint == "uptimely.library.merge.polars:merge_by_grain":
            arguments["key_columns"] = fragment.keys
        result = merge_module.Merge(dataset, fragment).execute(
            functools.partial(self._invoke, invocation, arguments=arguments),
            description=(
                f"Merge result {invocation.function_id} for profile {dataset_id}, "
                f"operator {invocation.operator_id}, invocation {invocation.id}"
            ),
            column_types=invocation.column_types,
            validate=self.validate,
        )

        dataset.dataframe = result
        dataset.fragments[invocation.operator_id] = fragment
        self.state.datasets[dataset_id] = dataset
        del self.state.staged_fragments[fragment_id]

    def _execute_column_operator(self, invocation: plan_module.Invocation) -> None:
        """Publish vectorized columns on the target frame without fragment assembly."""
        dataset_id = self._profile_id(invocation)
        dataset = self.state.datasets.get(dataset_id)
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
            (dataset_id, output): self.backend.select(
                frame, [*invocation.target_identifiers, output]
            )
            for output in output_features
        }
        dataset.dataframe = frame
        self.state.calculated_outputs.update(calculated_outputs)

    def _execute_target_operator(self, invocation: plan_module.Invocation) -> None:
        """Publish a complete target dataframe returned without a merge binding."""
        dataset_id = self._profile_id(invocation)
        frame = self._invoke(invocation)
        context = (
            f"target result from operator {invocation.operator_id}, "
            f"function {invocation.function_id}, invocation {invocation.id}, "
            f"profile {dataset_id}"
        )
        logger.debug("Check dataframe type for %s", context)
        if not self.backend.is_frame(frame):
            raise ValueError(
                f"Target result from {invocation.function_id} must be "
                "a Polars DataFrame or LazyFrame"
            )

        frame_columns = set(self.backend.column_names(frame))
        missing_identifiers = sorted(set(invocation.target_identifiers) - frame_columns)
        if missing_identifiers:
            raise ValueError(
                f"Target result from {invocation.function_id} is missing identifier columns: "
                + ", ".join(missing_identifiers)
            )
        output_features = [
            output
            for output in invocation.output_features
            if output not in invocation.target_identifiers
        ]
        missing_outputs = sorted(set(output_features) - frame_columns)
        if missing_outputs:
            raise ValueError(
                f"Operator {invocation.operator_id} is missing output columns: "
                + ", ".join(missing_outputs)
            )

        relations = [
            column
            for column in invocation.fragment_keys
            if column not in invocation.target_identifiers and column in frame_columns
        ]
        columns = list(
            dict.fromkeys([*invocation.target_identifiers, *relations, *output_features])
        )
        target = self.backend.select(frame, columns)
        dataset = dataset_module.Dataset(
            self.backend, invocation.target_identifiers, relations=relations
        )
        dataset.validate_frame(
            target,
            description=f"Target result for profile {dataset_id}",
            column_types=invocation.column_types,
            validate_content=self.validate,
        )
        calculated_outputs = {
            (dataset_id, output): self.backend.select(
                target, [*invocation.target_identifiers, output]
            )
            for output in output_features
        }
        dataset.dataframe = target
        self.state.datasets[dataset_id] = dataset
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
        description = f"Target transform result {invocation.function_id}"
        context = (
            f"target transform result from operator {invocation.operator_id}, "
            f"function {invocation.function_id}, invocation {invocation.id}, "
            f"profile {invocation.profile_id}"
        )
        logger.debug("Check dataframe type for %s", context)
        if not self.backend.is_frame(frame):
            raise ValueError(f"{description} must be a Polars DataFrame or LazyFrame")
        logger.debug(
            "Check required identifier columns %s for %s", invocation.target_identifiers, context
        )
        frame_columns = set(self.backend.column_names(frame))
        missing_identifiers = sorted(set(invocation.target_identifiers) - frame_columns)
        if missing_identifiers:
            raise ValueError(
                f"{description} is missing identifier columns: " + ", ".join(missing_identifiers)
            )

        output_features = [
            output
            for output in invocation.output_features
            if output not in invocation.target_identifiers
        ]
        logger.debug("Check declared output columns %s exist in %s", output_features, context)
        missing_outputs = sorted(set(output_features) - frame_columns)
        if missing_outputs:
            raise ValueError(
                f"Operator {invocation.operator_id} is missing output columns: "
                + ", ".join(missing_outputs)
            )

        existing_columns = set(self.backend.column_names(comparison_frame))
        existing_features = existing_columns - set(invocation.target_identifiers)
        logger.debug(
            "Check output columns %s do not replace existing feature columns %s in %s",
            output_features,
            sorted(existing_features),
            context,
        )
        collisions = sorted(set(output_features) & existing_features)
        if collisions:
            raise ValueError(
                f"Operator {invocation.operator_id} cannot replace existing "
                "columns: " + ", ".join(collisions)
            )

        logger.debug(
            "Check existing columns %s remain present in %s", sorted(existing_columns), context
        )
        missing_existing = sorted(existing_columns - frame_columns)
        if missing_existing:
            raise ValueError(
                f"Operator {invocation.operator_id} must preserve existing "
                "columns: " + ", ".join(missing_existing)
            )

        allowed_columns = existing_columns | set(output_features)
        logger.debug(
            "Check %s contains no columns outside existing and declared outputs %s",
            context,
            sorted(allowed_columns),
        )
        unexpected = sorted(frame_columns - allowed_columns)
        if unexpected:
            raise ValueError(
                f"Vectorize operator {invocation.operator_id} returned undeclared columns: "
                + ", ".join(unexpected)
            )

        if preserve_data:
            if (
                invocation.row_order_relation == "preserve"
                or invocation.existing_data_relation == "preserve"
            ):
                existing_names = self.backend.column_names(comparison_frame)
                logger.debug(
                    "Check values and row order of existing columns %s are unchanged in %s",
                    existing_names,
                    context,
                )
                if not self.backend.same_data(comparison_frame, frame, existing_names):
                    raise ValueError(
                        f"Operator {invocation.operator_id} must preserve existing "
                        "column values and row order"
                    )
            column_types = {
                name: invocation.column_types[name]
                for name in [*invocation.target_identifiers, *output_features]
                if name in invocation.column_types
            }
            logger.debug(
                "Check declared types of dimension and output columns %s in %s",
                column_types,
                context,
            )
            self.backend.validate_types(frame, column_types)
        return output_features

    @staticmethod
    def _profile_id(invocation: plan_module.Invocation) -> str:
        """Require a target profile ID for a dataframe invocation."""
        if invocation.profile_id is None:
            raise ValueError(f"Dataframe invocation {invocation.id} must declare a profile ID")
        return invocation.profile_id

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
