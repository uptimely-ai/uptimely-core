"""Invoke individual plan callables during an engine execution."""

import typing

from uptimely import entrypoint as entrypoint_module
from uptimely.compiler import plan as plan_module
from uptimely.spec import arg_types, operations
from uptimely.spec import model as spec_model

from . import backend as backend_module
from . import bindings as bindings_module
from . import dataframe as dataframe_module
from . import state as state_module


class CallableExecutor:
    """Dispatch and invoke callables against one execution's runtime state."""

    def __init__(
        self,
        backend: backend_module.DataFrameBackend,
        spec_definition: spec_model.Spec,
        entrypoints: typing.Mapping[str, entrypoint_module.Entrypoint],
        bind: typing.Mapping[str, typing.Mapping[str, typing.Mapping[str, typing.Any]]],
        state: state_module.RuntimeState,
    ) -> None:
        """Create a callable executor for one plan execution."""
        self.backend = backend
        self.spec_definition = spec_definition
        self.entrypoints = entrypoints
        self.state = state
        self.bindings = bindings_module.RuntimeBindings(spec_definition, state, bind)
        self.dataframe = dataframe_module.DataFrameExecution(backend, spec_definition, state)

    def execute(self, callable: plan_module.Callable) -> None:
        """Dispatch and execute one callable."""
        if callable.operation == operations.ESCAPE:
            self._execute_escape(callable)
            return

        self.dataframe.validate_inputs(callable)
        return_kind = operations.OPERATION_RETURN_KINDS.get(callable.operation)
        if return_kind == arg_types.DATAFRAME:
            self._execute_dataframe_mapping(callable)
        elif return_kind == "none":
            self._execute_sink(callable)
        else:
            raise ValueError(f"Unsupported callable operation: {callable.operation}")

    def _execute_dataframe_mapping(self, callable: plan_module.Callable) -> None:
        """Invoke a data-producing mapping, validate its result, and update the dataset."""
        frame = self.state.datasets.get(callable.dataset_id)
        result = self._invoke(callable)
        entity = self.spec_definition.entities.get(callable.entity_id)
        if entity is None:
            raise ValueError(f"Unknown entity: {callable.entity_id}")
        dimensions = entity.dimension_ids
        self.dataframe.validate_result(callable, result, frame, dimensions)
        columns = list(dict.fromkeys([*dimensions, *callable.output_features]))
        fragment = self.backend.select(result, columns)
        merged = self.dataframe.merge_fragment(frame, fragment, dimensions)

        self.state.datasets[callable.dataset_id] = merged
        self.state.fragments[(callable.dataset_id, callable.output or callable.id)] = fragment
        if callable.operation == operations.VECTORIZE:
            for output in callable.output_features:
                self.state.calculated_outputs[(callable.dataset_id, output)] = self.backend.select(
                    fragment, [*dimensions, output]
                )

    def _execute_escape(self, callable: plan_module.Callable) -> None:
        """Invoke an uncontrolled mapping and discard its return value."""
        self._invoke(callable)

    def _execute_sink(self, callable: plan_module.Callable) -> None:
        """Invoke a sink after confirming its accumulated dataset exists."""
        if callable.dataset_id not in self.state.datasets:
            raise KeyError(callable.dataset_id)
        self._invoke(callable)

    def _invoke(self, callable: plan_module.Callable) -> object:
        """Resolve arguments and invoke the callable's entrypoint."""
        kwargs = self.bindings.resolve_args(callable)
        entrypoint = self.entrypoints.get(callable.entrypoint)
        if entrypoint is None:
            entrypoint = entrypoint_module.Entrypoint(callable.entrypoint)
        function = entrypoint.load()
        return function(**kwargs)
