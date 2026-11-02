"""Invoke individual plan invocations during an engine execution."""

import collections
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
        *,
        validate: bool = False,
    ) -> None:
        """Create an invocation executor with opt-in per-step validation."""
        self.backend = backend
        self.spec_definition = spec_definition
        self.entrypoints = entrypoints
        self.state = state
        self.validate = validate
        self.bindings = bindings_module.RuntimeBindings(spec_definition, state, parameters)
        self.dataframe = dataframe_module.DataFrameExecution(
            backend, spec_definition, state, validate=validate
        )

    def execute(self, invocation: execution_plan.Invocation) -> None:
        """Dispatch and execute one invocation."""
        kind_definition = functions.FUNCTION_KINDS.get(invocation.function_kind)
        if kind_definition is None:
            raise ValueError(f"Unsupported invocation function kind: {invocation.function_kind}")
        if kind_definition.is_effect:
            self._invoke(invocation)
            return

        if self.validate:
            self._validate_inputs(invocation)
        if kind_definition.is_sink:
            self._execute_sink(invocation)
        elif kind_definition.returns == arg_types.DATAFRAME:
            self._execute_dataframe_action(invocation)
        else:
            raise ValueError(f"Unsupported invocation function kind: {invocation.function_kind}")

    def _validate_inputs(self, invocation: execution_plan.Invocation) -> None:
        """Require declared input features to be available in their allowed scope."""
        function = self.spec_definition.functions.get(invocation.function_id)
        if function is None:
            raise ValueError(f"Unknown function: {invocation.function_id}")
        definition = functions.FUNCTION_KINDS[function.kind]
        if definition.dataframe_input_scope == "foreign":
            self._validate_foreign_inputs(invocation, function)
            return

        target = self.state.datasets.get(invocation.dataset_id)
        target_columns = set(self.backend.column_names(target)) if target is not None else set()
        required = set(invocation.input_features) - target_columns
        if not required:
            return
        available = collections.Counter(
            column
            for dataset_id, frame in self.state.datasets.items()
            if dataset_id != invocation.dataset_id
            for column in set(self.backend.column_names(frame))
        )
        for feature in invocation.input_features:
            if feature not in required:
                continue
            if available[feature] != 1:
                raise ValueError(
                    f"Action {invocation.mapping_id} input feature is unavailable or ambiguous: "
                    f"{feature}"
                )

    def _validate_foreign_inputs(
        self,
        invocation: execution_plan.Invocation,
        function: spec_model.FunctionTemplate,
    ) -> None:
        """Check declared feature inputs against their foreign dataframe."""
        dataframe_arguments = function.arguments_by_type.get(arg_types.DATAFRAME, {})
        if len(dataframe_arguments) != 1:
            raise ValueError(
                f"Action {invocation.mapping_id} must declare exactly one foreign "
                "dataframe argument"
            )
        argument_name = next(iter(dataframe_arguments))
        source_id = invocation.arguments.get(argument_name)
        if not isinstance(source_id, str) or source_id == invocation.dataset_id:
            raise ValueError(
                f"Action {invocation.mapping_id} must reference a foreign source dataset"
            )
        source = self.state.datasets.get(source_id)
        if source is None:
            raise ValueError(f"Dataset dataframe is unavailable: {source_id}")

        source_columns = set(self.backend.column_names(source))
        for feature in invocation.input_features:
            if feature not in source_columns:
                raise ValueError(
                    f"Action {invocation.mapping_id} input feature is unavailable in foreign "
                    f"source dataset: {feature}"
                )

    def _execute_dataframe_action(self, invocation: execution_plan.Invocation) -> None:
        """Invoke a data-producing action, validate its result, and update the dataset."""
        dataframe = self.state.datasets.get(invocation.dataset_id)
        fragment = self._invoke(invocation)
        dataset_key = (invocation.entity_id, invocation.dataset_id)
        if (
            invocation.dataset_id is not None
            and dataset_key in self.spec_definition.datasets_by_key
        ):
            dimensions = self.spec_definition.dimension_ids_by_dataset[invocation.dataset_id]
        else:
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
        kind_definition = functions.FUNCTION_KINDS[invocation.function_kind]
        if kind_definition.is_transformer:
            for output in invocation.output_features:
                self.state.calculated_outputs[(invocation.dataset_id, output)] = (
                    self.backend.select(fragment, [*dimensions, output])
                )

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
