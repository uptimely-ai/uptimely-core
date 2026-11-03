"""Validate invocation inputs against the current execution state."""

from __future__ import annotations

import collections
import dataclasses
import logging
import typing

from uptimely import execution_plan
from uptimely.engine.dataframe import backend as backend_module
from uptimely.spec import arg_types, functions

if typing.TYPE_CHECKING:
    from uptimely.engine.dataframe import main_frame as main_frame_module

    from . import state as state_module

logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class InvocationValidator:
    """Validate an invocation's data-input requirements against runtime state.

    Check foreign dataframe arguments, source references, source availability,
    and required features, or resolve features locally or uniquely across
    datasets. Argument binding and returned-data validation are handled elsewhere.
    """

    backend: backend_module.DataFrameBackend
    state: state_module.RuntimeState
    invocation: execution_plan.Invocation

    def validate(self) -> None:
        """Check input scope and feature availability in fail-fast order.

        Raises:
            ValueError: A source reference is invalid or required features are
                unavailable or ambiguous.
        """
        logger.debug("  Requirements:")
        definition = functions.FUNCTION_KINDS[self.invocation.function_kind]
        if definition.dataframe_input_scope == "foreign":
            self._validate_foreign_dataframe_argument()
            source_id = self._validate_foreign_source_reference()
            source = self._validate_foreign_source_available(source_id)
            self._validate_foreign_input_features(source)
        else:
            self._validate_input_features()

    def _validate_input_features(self) -> None:
        """Require each feature locally or in exactly one other profile."""
        logger.debug("    - checking declared input features")
        invocation = self.invocation
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

    @property
    def dataframe_arguments(self) -> list[str]:
        """Return names of declared dataframe arguments."""
        return [
            name
            for name, argument_type in self.invocation.argument_types.items()
            if argument_type == arg_types.DATAFRAME
        ]

    def _validate_foreign_dataframe_argument(self) -> None:
        """Require exactly one dataframe argument for a foreign input."""
        logger.debug("    - checking foreign dataframe argument")
        if len(self.dataframe_arguments) != 1:
            raise ValueError(
                f"Action {self.invocation.mapping_id} must declare exactly one foreign "
                "dataframe argument"
            )

    def _validate_foreign_source_reference(self) -> str:
        """Require a dataset reference distinct from the invocation's target.

        Returns:
            The validated foreign dataset ID.

        Raises:
            ValueError: The argument is not a foreign dataset reference.
        """
        logger.debug("    - checking foreign source reference")
        invocation = self.invocation
        source_id = invocation.arguments.get(self.dataframe_arguments[0])
        if not isinstance(source_id, str) or source_id == invocation.dataset_id:
            raise ValueError(
                f"Action {invocation.mapping_id} must reference a foreign source profile"
            )
        return source_id

    def _validate_foreign_source_available(self, source_id: str) -> main_frame_module.MainFrame:
        """Require the referenced dataset to be available in runtime state.

        Args:
            source_id: Validated foreign dataset reference.

        Returns:
            The available source main frame.

        Raises:
            ValueError: The referenced source has not been produced.
        """
        logger.debug("    - checking foreign source availability")
        source = self.state.main_frames.get(source_id)
        if source is None:
            raise ValueError(f"Profile dataframe is unavailable: {source_id}")
        return source

    def _validate_foreign_input_features(self, source: main_frame_module.MainFrame) -> None:
        """Require declared features in the validated foreign source.

        Args:
            source: Available source main frame.

        Raises:
            ValueError: A required feature is missing from the source.
        """
        logger.debug("    - checking foreign input features")
        invocation = self.invocation
        columns = set(self.backend.column_names(source.dataframe))
        for feature in invocation.input_features:
            if feature not in columns:
                raise ValueError(
                    f"Action {invocation.mapping_id} input feature is unavailable in foreign "
                    f"source profile: {feature}"
                )
