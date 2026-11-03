"""Invoke plan operations and commit their fragments to profile main frames."""

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
    """Dispatch invocations and accumulate their results in per-profile main frames."""

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
        if definition.is_sink:
            if invocation.dataset_id not in self.state.main_frames:
                raise KeyError(invocation.dataset_id)
            self._invoke(invocation)
        elif definition.returns == arg_types.DATAFRAME:
            self._execute_dataframe_action(invocation)
        else:
            raise ValueError(f"Unsupported invocation function kind: {invocation.function_kind}")

    def _execute_dataframe_action(self, invocation: execution_plan.Invocation) -> None:
        """Produce a fragment and merge it into the target profile's main frame."""
        dataset_id = invocation.dataset_id
        if dataset_id is None:
            raise ValueError(f"Dataframe invocation {invocation.id} must declare a profile ID")
        main_frame = self.state.main_frames.get(dataset_id)
        fragment = fragment_module.Fragment.stage(
            self.backend,
            invocation,
            functools.partial(self._invoke, invocation),
            validate=self.validate,
            comparison_frame=main_frame.dataframe if main_frame is not None else None,
        )
        fragment = self._merge_fragment(invocation, fragment)
        definition = functions.FUNCTION_KINDS[invocation.function_kind]
        if definition.is_transformer:
            for output in invocation.output_features:
                self.state.calculated_outputs[(dataset_id, output)] = self.backend.select(
                    fragment.dataframe, [*invocation.id_columns, output]
                )

    def _merge_fragment(
        self, invocation: execution_plan.Invocation, fragment: fragment_module.Fragment
    ) -> fragment_module.Fragment:
        """Check assembly contracts and commit a staged fragment to physical data."""
        dataset_id = invocation.dataset_id
        if dataset_id is None:
            raise ValueError(f"Dataframe invocation {invocation.id} must declare a profile ID")
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
            fragment_id=fragment.invocation.mapping_id if fragment.invocation is not None else None,
            join_cardinality="1:1" if self.validate else "m:m",
            broadcast_cardinality="m:1" if self.validate else "m:m",
        )
        self.state.main_frames[dataset_id] = main_frame
        return fragment

    def _invoke(self, invocation: execution_plan.Invocation) -> object:
        """Resolve arguments and invoke the entrypoint for one plan invocation."""
        kwargs = self.bindings.resolve_args(invocation)
        entrypoint = self.entrypoints.get(invocation.entrypoint)
        if entrypoint is None:
            entrypoint = entrypoint_module.Entrypoint(invocation.entrypoint)
        return entrypoint.load()(**kwargs)
