"""Per-execution validation policies for invocations and dataframe assembly."""

from __future__ import annotations

import collections
import typing

from uptimely import execution_plan
from uptimely.engine.dataframe import backend as backend_module
from uptimely.engine.dataframe import validation as dataframe_validation
from uptimely.spec import arg_types, functions

if typing.TYPE_CHECKING:
    from . import state as state_module


class ValidationPolicy:
    """Provide no-op hooks for normal execution without runtime contract checks."""

    join_cardinality = "m:m"
    broadcast_cardinality = "m:m"

    def before_invocation(self, invocation: execution_plan.Invocation) -> None:
        """Check declared input features before a non-effect invocation."""

    def validate_fragment(self, context: dataframe_validation.FrameValidationContext) -> None:
        """Check the raw fragment before projection."""

    def validate_accumulated(
        self, frame: object | None, invocation: execution_plan.Invocation
    ) -> None:
        """Check the existing main dataframe before merging."""

    def before_join(self, dataframe: object, fragment: object, dimensions: list[str]) -> None:
        """Check feature collisions before joining dataframes."""


class StepValidation(ValidationPolicy):
    """Enforce input and dataframe contracts at the execution boundaries."""

    join_cardinality = "1:1"
    broadcast_cardinality = "m:1"

    def __init__(
        self,
        backend: backend_module.DataFrameBackend,
        state: state_module.RuntimeState,
    ) -> None:
        """Bind validation to one execution's backend and runtime state."""
        self.backend = backend
        self.state = state

    def before_invocation(self, invocation: execution_plan.Invocation) -> None:
        """Require declared input features in their allowed scope."""
        definition = functions.FUNCTION_KINDS[invocation.function_kind]
        if definition.dataframe_input_scope == "foreign":
            self._validate_foreign_inputs(invocation)
            return
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
                    f"Action {invocation.mapping_id} input feature is unavailable or ambiguous: "
                    f"{feature}"
                )

    def _validate_foreign_inputs(self, invocation: execution_plan.Invocation) -> None:
        """Validate declared feature inputs against the foreign source dataframe."""
        arguments = [
            name
            for name, argument_type in invocation.argument_types.items()
            if argument_type == arg_types.DATAFRAME
        ]
        if len(arguments) != 1:
            raise ValueError(
                f"Action {invocation.mapping_id} must declare exactly one foreign "
                "dataframe argument"
            )
        source_id = invocation.arguments.get(arguments[0])
        if not isinstance(source_id, str) or source_id == invocation.dataset_id:
            raise ValueError(
                f"Action {invocation.mapping_id} must reference a foreign source dataset"
            )
        source = self.state.main_frames.get(source_id)
        if source is None:
            raise ValueError(f"Dataset dataframe is unavailable: {source_id}")
        columns = set(self.backend.column_names(source.dataframe))
        for feature in invocation.input_features:
            if feature not in columns:
                raise ValueError(
                    f"Action {invocation.mapping_id} input feature is unavailable in foreign "
                    f"source dataset: {feature}"
                )

    def validate_fragment(self, context: dataframe_validation.FrameValidationContext) -> None:
        """Apply shared contract rules to an invocation result or standalone fragment."""
        if context.invocation is None:
            dataframe_validation.validate_frame_structure(
                self.backend,
                context.frame,
                context.dimensions,
                context.description,
            )
        else:
            dataframe_validation.validate_fragment(context)

    def validate_accumulated(
        self, frame: object | None, invocation: execution_plan.Invocation
    ) -> None:
        """Validate the main dataframe's structure and declared types."""
        if frame is None:
            return
        dataframe_validation.validate_frame_structure(
            self.backend, frame, invocation.id_columns, "Accumulated dataset"
        )
        columns = set(self.backend.column_names(frame))
        dataframe_validation.validate_dataframes(
            dataframe_validation.FrameValidationContext(
                self.backend,
                frame,
                invocation.id_columns,
                "Accumulated dataset",
                declared_type_columns=[name for name in invocation.column_types if name in columns],
                column_types=invocation.column_types,
            ),
            (dataframe_validation.validate_dataset_declared_types,),
        )

    def before_join(self, dataframe: object, fragment: object, dimensions: list[str]) -> None:
        """Reject overlapping feature columns before joining."""
        dataframe_validation.validate_feature_collisions(
            self.backend, dataframe, fragment, dimensions
        )


def create_policy(
    validate: bool,
    backend: backend_module.DataFrameBackend,
    state: state_module.RuntimeState,
) -> ValidationPolicy:
    """Select a shared runtime validation policy once per execution."""
    if validate:
        return StepValidation(backend, state)
    return ValidationPolicy()
