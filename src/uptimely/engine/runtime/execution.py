"""Invoke plan operations and publish their results to profile main frames."""

import functools
import logging
import typing

from uptimely import entrypoint as entrypoint_module
from uptimely import execution_plan
from uptimely.engine.dataframe import backend as backend_module
from uptimely.engine.dataframe import fragment as fragment_module
from uptimely.engine.dataframe import main_frame as main_frame_module
from uptimely.engine.dataframe import validation as dataframe_validation
from uptimely.spec import arg_types, functions

from . import bindings as bindings_module
from . import state as state_module
from . import validation as validation_module

logger = logging.getLogger(__name__)


class InvocationExecutor:
    """Dispatch invocations and publish results into per-profile main frames."""

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

    def execute(self, invocation: execution_plan.Invocation) -> None:
        """Execute one invocation, validating before side effects and state updates."""
        definition = functions.FUNCTION_KINDS.get(invocation.function_kind)
        if definition is None:
            raise ValueError(f"Unsupported invocation function kind: {invocation.function_kind}")
        if definition.is_effect:
            self._invoke(invocation)
            return
        if self.validate:
            validation_module.InvocationValidator(self.backend, self.state, invocation).validate()
        if definition.returns == arg_types.DATAFRAME:
            if definition.produces_fragment:
                self._execute_dataframe_operator(invocation)
            else:
                self._execute_column_operator(invocation)
        else:
            if invocation.dataset_id not in self.state.main_frames:
                raise KeyError(invocation.dataset_id)
            self._invoke(invocation)

    def _execute_dataframe_operator(self, invocation: execution_plan.Invocation) -> None:
        """Produce a fragment and merge it into the target profile's main frame."""
        dataset_id = self._profile_id(invocation)
        main_frame = self.state.main_frames.get(dataset_id)
        fragment = fragment_module.Fragment.stage(
            self.backend,
            invocation,
            functools.partial(self._invoke, invocation),
            validate=self.validate,
            comparison_frame=main_frame.dataframe if main_frame is not None else None,
        )
        self._merge_fragment(invocation, fragment)

    def _execute_column_operator(self, invocation: execution_plan.Invocation) -> None:
        """Publish vectorized columns on the target frame without fragment assembly."""
        dataset_id = self._profile_id(invocation)
        main_frame = self.state.main_frames.get(dataset_id)
        if main_frame is None or main_frame.dataframe is None:
            raise ValueError(f"Profile dataframe is unavailable: {dataset_id}")
        comparison_frame = main_frame.dataframe
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
        validator = dataframe_validation.ColumnsValidator(
            self.backend,
            frame,
            invocation.id_columns,
            f"Vectorize result {invocation.function_id}",
            column_types=invocation.column_types,
            invocation=invocation,
            comparison_frame=comparison_frame,
        )
        validator.validate(preserve_data=self.validate)
        calculated_outputs = {
            (dataset_id, output): self.backend.select(frame, [*invocation.id_columns, output])
            for output in validator.output_features
        }
        main_frame.dataframe = frame
        self.state.calculated_outputs.update(calculated_outputs)

    def _merge_fragment(
        self, invocation: execution_plan.Invocation, fragment: fragment_module.Fragment
    ) -> fragment_module.Fragment:
        """Check assembly contracts and commit a staged fragment to physical data."""
        dataset_id = self._profile_id(invocation)
        main_frame = self.state.main_frames.get(dataset_id)
        if main_frame is None:
            main_frame = main_frame_module.MainFrame(
                self.backend,
                invocation.id_columns,
            )
        validator = None
        if self.validate and main_frame.dataframe is not None:
            validator = dataframe_validation.MainFrameValidator(
                self.backend,
                main_frame.dataframe,
                invocation.id_columns,
                "Accumulated profile",
                column_types=invocation.column_types,
            )
            validator.validate()
        logger.debug("  Merge:\n    Target profile: %s", dataset_id)
        if validator is not None:
            validator.validate_merge(fragment.dataframe)
        main_frame.merge(
            fragment,
            fragment_id=(
                fragment.invocation.operator_id if fragment.invocation is not None else None
            ),
            join_cardinality="1:1" if self.validate else "m:m",
            broadcast_cardinality="m:1" if self.validate else "m:m",
        )
        self.state.main_frames[dataset_id] = main_frame
        return fragment

    @staticmethod
    def _profile_id(invocation: execution_plan.Invocation) -> str:
        """Require a target profile ID for a dataframe invocation."""
        if invocation.dataset_id is None:
            raise ValueError(f"Dataframe invocation {invocation.id} must declare a profile ID")
        return invocation.dataset_id

    def _invoke(
        self,
        invocation: execution_plan.Invocation,
        *,
        arguments: typing.Mapping[str, object] | None = None,
    ) -> object:
        """Resolve arguments and invoke the entrypoint for one plan invocation."""
        kwargs = self.bindings.resolve_args(invocation) if arguments is None else arguments
        entrypoint = self.entrypoints.get(invocation.entrypoint)
        if entrypoint is None:
            entrypoint = entrypoint_module.Entrypoint(invocation.entrypoint)
        return entrypoint.load()(**kwargs)
