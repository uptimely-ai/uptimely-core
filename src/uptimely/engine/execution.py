"""Invoke individual plan callables during an engine execution."""

import pathlib
import typing

from uptimely import contracts
from uptimely import entrypoint as entrypoint_module
from uptimely.compiler import plan as plan_module

from . import backend as backend_module
from . import bindings as bindings_module
from . import dataframe as dataframe_module
from . import state as state_module


class CallableExecutor:
    """Dispatch and invoke callables against one execution's runtime state."""

    def __init__(
        self,
        project_root: pathlib.Path,
        backend: backend_module.DataFrameBackend,
        resources: typing.Mapping[str, typing.Any],
        bind: typing.Mapping[str, typing.Mapping[str, typing.Mapping[str, typing.Any]]],
        state: state_module.RuntimeState,
    ) -> None:
        """Create a callable executor for one plan execution."""
        self.project_root = project_root
        self.backend = backend
        self.resources = resources
        self.state = state
        self.bindings = bindings_module.RuntimeBindings(resources, state, bind)
        self.dataframe = dataframe_module.DataFrameExecution(backend, resources, state)

    def execute(self, callable: plan_module.Callable) -> None:
        """Dispatch and execute one callable."""
        if callable.operation == "escape":
            self._execute_escape(callable)
            return

        self.dataframe.validate_inputs(callable)
        return_kind = contracts.OPERATION_RETURN_KINDS.get(callable.operation)
        if return_kind == "dataframe":
            self._execute_dataframe_mapping(callable)
        elif return_kind == "none":
            self._execute_sink(callable)
        else:
            raise ValueError(f"Unsupported callable operation: {callable.operation}")

    def _execute_dataframe_mapping(self, callable: plan_module.Callable) -> None:
        """Invoke a data-producing mapping, validate its result, and update the dataset."""
        dataset_key = (callable.entity_id, callable.dataset_id)
        frame = self.state.datasets.get(dataset_key)
        result = self._invoke(callable)
        entity = self.resources.get("entities", {}).get(callable.entity_id)
        if entity is None:
            raise ValueError(f"Unknown entity: {callable.entity_id}")
        dimensions = list(entity.get("dimensions", []))
        self.dataframe.validate_result(callable, result, frame, dimensions)
        columns = list(dict.fromkeys([*dimensions, *callable.output_features]))
        fragment = self.backend.select(result, columns)
        merged = self.dataframe.merge_fragment(frame, fragment, dimensions)

        self.state.datasets[dataset_key] = merged
        self.state.fragments[(callable.entity_id, callable.output or callable.id)] = fragment
        if callable.operation == "vectorize":
            for output in callable.output_features:
                self.state.calculated_outputs[(*dataset_key, output)] = self.backend.select(
                    fragment, [*dimensions, output]
                )

    def _execute_escape(self, callable: plan_module.Callable) -> None:
        """Invoke an uncontrolled mapping and discard its return value."""
        self._invoke(callable)

    def _execute_sink(self, callable: plan_module.Callable) -> None:
        """Invoke a sink after confirming its accumulated dataset exists."""
        dataset_key = (callable.entity_id, callable.dataset_id)
        if dataset_key not in self.state.datasets:
            raise KeyError(dataset_key)
        self._invoke(callable)

    def _invoke(self, callable: plan_module.Callable) -> object:
        """Resolve arguments and invoke the callable's entrypoint."""
        kwargs = self.bindings.resolve_args(callable)
        function = entrypoint_module.Entrypoint(
            callable.entrypoint, self.project_root
        ).function.load()
        return function(**kwargs)
