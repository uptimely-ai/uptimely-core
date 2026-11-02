"""Validate invocation inputs against the current execution state."""

from __future__ import annotations

import collections
import typing

from uptimely import execution_plan
from uptimely.engine.dataframe import backend as backend_module
from uptimely.spec import arg_types, functions

if typing.TYPE_CHECKING:
    from . import state as state_module


class InvocationValidator:
    """Check declared feature inputs before invoking a non-effect action."""

    def __init__(
        self,
        backend: backend_module.DataFrameBackend,
        state: state_module.RuntimeState,
    ) -> None:
        """Bind validation to one execution's backend and runtime state."""
        self.backend = backend
        self.state = state

    def validate(self, invocation: execution_plan.Invocation) -> None:
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
