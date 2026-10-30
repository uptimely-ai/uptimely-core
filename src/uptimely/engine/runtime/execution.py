"""Invoke individual plan invocations during an engine execution."""

import typing

from uptimely import entrypoint as entrypoint_module
from uptimely import execution_plan
from uptimely.spec import arg_types, functions
from uptimely.spec import model as spec_model

from ..dataframe import backend as backend_module
from ..dataframe import dataframe as dataframe_module
from . import bindings as bindings_module
from . import state as state_module


class InvocationExecutor:
    """Dispatch and execute invocations against one execution's runtime state."""

    def __init__(
        self,
        backend: backend_module.DataFrameBackend,
        spec_definition: spec_model.Spec,
        entrypoints: typing.Mapping[str, entrypoint_module.Entrypoint],
        parameters: typing.Mapping[str, typing.Any],
        state: state_module.RuntimeState,
    ) -> None:
        """Create an invocation executor for one plan execution."""
        self.backend = backend
        self.spec_definition = spec_definition
        self.entrypoints = entrypoints
        self.state = state
        self.bindings = bindings_module.RuntimeBindings(spec_definition, state, parameters)
        self.dataframe = dataframe_module.DataFrameExecution(backend, spec_definition, state)

    def execute(self, invocation: execution_plan.Invocation) -> None:
        """Dispatch and execute one invocation."""
        function_kind = functions.FUNCTION_KINDS.get(invocation.function_kind)
        if function_kind is None:
            raise ValueError(f"Unsupported invocation function kind: {invocation.function_kind}")
        if function_kind.is_effect:
            self._execute_escape(invocation)
            return

        self.dataframe.validate_inputs(invocation)
        return_kind = function_kind.returns
        if return_kind == arg_types.DATAFRAME:
            self._execute_dataframe_action(invocation)
        elif return_kind == "none":
            self._execute_sink(invocation)
        else:
            raise ValueError(f"Unsupported invocation function kind: {invocation.function_kind}")

    def _execute_dataframe_action(self, invocation: execution_plan.Invocation) -> None:
        """Invoke a data-producing action, validate its result, and update the dataset."""
        dataframe = self.state.datasets.get(invocation.dataset_id)
        fragment = self._invoke(invocation)
        entity = self.spec_definition.entities.get(invocation.entity_id)
        if entity is None:
            raise ValueError(f"Unknown entity: {invocation.entity_id}")
        dimensions = entity.dimension_ids
        fragment, dataframe = self.dataframe.assemble_fragment(
            invocation, fragment, dataframe, dimensions
        )

        if dataframe is not None:
            self.state.datasets[invocation.dataset_id] = dataframe
        self.state.fragments[(invocation.dataset_id, invocation.mapping_id)] = fragment
        if invocation.function_kind == functions.VECTORIZE:
            for output in invocation.output_features:
                self.state.calculated_outputs[(invocation.dataset_id, output)] = (
                    self.backend.select(fragment, [*dimensions, output])
                )

    def _execute_escape(self, invocation: execution_plan.Invocation) -> None:
        """Invoke an uncontrolled action and discard its return value."""
        self._invoke(invocation)

    def _execute_sink(self, invocation: execution_plan.Invocation) -> None:
        """Invoke a sink after confirming its accumulated dataset exists."""
        if invocation.dataset_id not in self.state.datasets:
            raise KeyError(invocation.dataset_id)
        self._invoke(invocation)

    def _invoke(self, invocation: execution_plan.Invocation) -> object:
        """Resolve arguments and invoke the entrypoint for one plan invocation."""
        kwargs = self.bindings.resolve_args(invocation)
        entrypoint = self.entrypoints.get(invocation.entrypoint)
        if entrypoint is None:
            entrypoint = entrypoint_module.Entrypoint(invocation.entrypoint)
        function = entrypoint.load()
        return function(**kwargs)
