"""Validate runtime dataframe inputs, results, and structural contracts."""

from __future__ import annotations

import collections.abc
import dataclasses
import graphlib

from uptimely import execution_plan
from uptimely.engine import backend as backend_module
from uptimely.engine import state as state_module
from uptimely.spec import arg_types, functions
from uptimely.spec import model as spec_model


@dataclasses.dataclass
class InputValidationContext:
    """Runtime resources needed to validate one invocation's input features."""

    backend: backend_module.DataFrameBackend
    spec_definition: spec_model.Spec
    state: state_module.RuntimeState
    invocation: execution_plan.Invocation
    function: spec_model.FunctionTemplate | None = None


@dataclasses.dataclass(frozen=True)
class FrameValidationContext:
    """One dataframe and its structural validation requirements."""

    backend: backend_module.DataFrameBackend
    spec_definition: spec_model.Spec
    frame: object
    dimensions: list[str]
    description: str
    invalid_frame_message: str | None = None
    invocation: execution_plan.Invocation | None = None
    output_features: list[str] | None = None
    dataset: spec_model.Dataset | None = None
    declared_type_columns: list[str] | None = None
    comparison_frame: object | None = None


type DataFrameValidationContext = InputValidationContext | FrameValidationContext
type Validator = collections.abc.Callable[[DataFrameValidationContext], None]


def validate_input_function(context: DataFrameValidationContext) -> None:
    """Resolve the function definition used by runtime input validation."""
    input_context = _require_input_context(context)
    function = input_context.spec_definition.functions.get(input_context.invocation.function_id)
    if function is None:
        raise ValueError(f"Unknown function: {input_context.invocation.function_id}")
    input_context.function = function


def validate_input_features(context: DataFrameValidationContext) -> None:
    """Require declared input features to be available in their allowed scope."""
    input_context = _require_input_context(context)
    function = _require_function(input_context)
    definition = functions.FUNCTION_KINDS[function.kind]
    if definition.dataframe_input_scope == "foreign":
        _validate_foreign_inputs(input_context, function)
        return

    invocation = input_context.invocation
    dataframe = input_context.state.datasets.get(invocation.dataset_id)
    dataframe_columns = (
        set(input_context.backend.column_names(dataframe)) if dataframe is not None else set()
    )
    required = set(invocation.input_features) - dataframe_columns
    if not required:
        return
    available = [
        set(input_context.backend.column_names(candidate_dataframe))
        for dataset_id, candidate_dataframe in input_context.state.datasets.items()
        if dataset_id != invocation.dataset_id
    ]
    for feature in invocation.input_features:
        if feature not in required:
            continue
        if sum(feature in columns for columns in available) != 1:
            raise ValueError(
                f"Action {invocation.mapping_id} input feature is unavailable or ambiguous: "
                f"{feature}"
            )


def validate_frame_type(context: DataFrameValidationContext) -> None:
    """Require a validated dataframe object before inspecting its schema."""
    frame_context = _require_frame_context(context)
    if not frame_context.backend.is_frame(frame_context.frame):
        raise ValueError(
            frame_context.invalid_frame_message
            or f"{frame_context.description} must be a Polars DataFrame or LazyFrame"
        )


def validate_dimension_columns(context: DataFrameValidationContext) -> None:
    """Require all dimension keys in a dataframe schema."""
    frame_context = _require_frame_context(context)
    columns = set(frame_context.backend.column_names(frame_context.frame))
    missing = sorted(set(frame_context.dimensions) - columns)
    if missing:
        raise ValueError(
            f"{frame_context.description} is missing dimension columns: " + ", ".join(missing)
        )


def validate_unique_dimension_keys(context: DataFrameValidationContext) -> None:
    """Reject duplicate observation keys when value validation is enabled."""
    frame_context = _require_frame_context(context)
    if not frame_context.backend.should_validate_values(frame_context.frame):
        return
    if not frame_context.dimensions:
        if frame_context.backend.row_count(frame_context.frame) > 1:
            raise ValueError(
                f"{frame_context.description} contains duplicate dimension keys "
                "(dimensionless datasets allow at most one row)"
            )
        return
    keys = frame_context.backend.select(frame_context.frame, frame_context.dimensions)
    if frame_context.backend.is_duplicated(keys):
        raise ValueError(f"{frame_context.description} contains duplicate dimension keys")


def validate_output_columns(context: DataFrameValidationContext) -> None:
    """Require every declared action output in the returned fragment."""
    frame_context = _require_frame_context(context)
    invocation = _require_invocation(frame_context)
    output_features = frame_context.output_features or invocation.output_features
    columns = set(frame_context.backend.column_names(frame_context.frame))
    missing = sorted(set(output_features) - columns)
    if missing:
        raise ValueError(
            f"Action {invocation.mapping_id} is missing output columns: " + ", ".join(missing)
        )


def validate_fragment_declared_types(context: DataFrameValidationContext) -> None:
    """Check declared logical types for a returned fragment's keys and outputs."""
    frame_context = _require_frame_context(context)
    dataset = _require_dataset(frame_context)
    output_features = (
        frame_context.output_features or _require_invocation(frame_context).output_features
    )
    _validate_declared_types(frame_context, dataset, [*frame_context.dimensions, *output_features])


def validate_dataset_declared_types(context: DataFrameValidationContext) -> None:
    """Check declared logical types for columns already present in an accumulated dataset."""
    frame_context = _require_frame_context(context)
    dataset = _require_dataset(frame_context)
    columns = frame_context.declared_type_columns
    if columns is None:
        raise TypeError("Dataset type validation requires declared type columns")
    _validate_declared_types(frame_context, dataset, columns)


def validate_key_coverage(context: DataFrameValidationContext) -> None:
    """Require vectorized fragments to cover the accumulated dataset's dimension keys."""
    frame_context = _require_frame_context(context)
    invocation = _require_invocation(frame_context)
    if invocation.function_kind != functions.VECTORIZE:
        return
    dataframe = frame_context.comparison_frame
    validate_coverage = (
        dataframe is not None
        and frame_context.backend.should_validate_values(dataframe)
        and frame_context.backend.should_validate_values(frame_context.frame)
    )
    if dataframe is None or (
        validate_coverage
        and not frame_context.backend.same_keys(
            dataframe, frame_context.frame, frame_context.dimensions
        )
    ):
        raise ValueError(
            f"Vectorize action {invocation.mapping_id} must preserve the dataset dimension keys"
        )


DATAFRAME_VALIDATION_DEPENDENCIES: dict[Validator, tuple[Validator, ...]] = {
    validate_input_function: (),
    validate_input_features: (validate_input_function,),
    validate_frame_type: (),
    validate_dimension_columns: (validate_frame_type,),
    validate_unique_dimension_keys: (validate_dimension_columns,),
    validate_output_columns: (validate_unique_dimension_keys,),
    validate_fragment_declared_types: (validate_output_columns,),
    validate_dataset_declared_types: (validate_dimension_columns,),
    validate_key_coverage: (validate_fragment_declared_types,),
}


def validate_dataframes(
    context: DataFrameValidationContext,
    validators: collections.abc.Iterable[Validator],
) -> None:
    """Run requested dataframe checks after their prerequisites succeed.

    Args:
        context: Runtime values required by the requested validators.
        validators: Validators applicable to the current engine operation.

    Raises:
        ValueError: A dataframe invariant is violated or a validator is unknown.
        graphlib.CycleError: Validator dependencies contain a configuration cycle.
    """
    requested = tuple(validators)
    if not requested:
        raise ValueError("At least one dataframe validator must be requested")

    selected: set[Validator] = set()

    def include(validator: Validator) -> None:
        if validator not in DATAFRAME_VALIDATION_DEPENDENCIES:
            raise ValueError(f"Unknown dataframe validator: {validator}")
        if validator in selected:
            return
        selected.add(validator)
        for prerequisite in DATAFRAME_VALIDATION_DEPENDENCIES[validator]:
            include(prerequisite)

    for validator in requested:
        include(validator)

    dependencies = {
        validator: tuple(prerequisite for prerequisite in prerequisites if prerequisite in selected)
        for validator, prerequisites in DATAFRAME_VALIDATION_DEPENDENCIES.items()
        if validator in selected
    }
    for validator in graphlib.TopologicalSorter(dependencies).static_order():
        validator(context)


def _validate_foreign_inputs(
    context: InputValidationContext, function: spec_model.FunctionTemplate
) -> None:
    """Check declared feature inputs against their foreign dataframe."""
    invocation = context.invocation
    dataframe_arguments = [
        name for name, argument in function.args.items() if argument.type == arg_types.DATAFRAME
    ]
    if len(dataframe_arguments) != 1:
        raise ValueError(
            f"Action {invocation.mapping_id} must declare exactly one foreign dataframe argument"
        )
    argument_name = dataframe_arguments[0]
    source_id = invocation.arguments.get(argument_name)
    if not isinstance(source_id, str) or source_id == invocation.dataset_id:
        raise ValueError(f"Action {invocation.mapping_id} must reference a foreign source dataset")
    source = context.state.datasets.get(source_id)
    if source is None:
        raise ValueError(f"Dataset dataframe is unavailable: {source_id}")

    source_columns = set(context.backend.column_names(source))
    for feature in invocation.input_features:
        if feature not in source_columns:
            raise ValueError(
                f"Action {invocation.mapping_id} input feature is unavailable in foreign "
                f"source dataset: {feature}"
            )


def _validate_declared_types(
    context: FrameValidationContext,
    dataset: spec_model.Dataset,
    columns: list[str],
) -> None:
    """Validate logical types declared for selected dataset columns."""
    types: dict[str, str] = {}
    for name in dict.fromkeys(columns):
        definition = context.spec_definition.dimensions.get(name) or dataset.features.get(name)
        if definition is not None and definition.type is not None:
            types[name] = definition.type
    context.backend.validate_types(context.frame, types)


def _require_input_context(
    context: DataFrameValidationContext,
) -> InputValidationContext:
    if not isinstance(context, InputValidationContext):
        raise TypeError("Input validation requires an input context")
    return context


def _require_function(context: InputValidationContext) -> spec_model.FunctionTemplate:
    if context.function is None:
        raise RuntimeError("Function reference validation must run before input validation")
    return context.function


def _require_frame_context(
    context: DataFrameValidationContext,
) -> FrameValidationContext:
    if not isinstance(context, FrameValidationContext):
        raise TypeError("Dataframe validation requires a dataframe context")
    return context


def _require_invocation(
    context: FrameValidationContext,
) -> execution_plan.Invocation:
    if context.invocation is None:
        raise TypeError("This dataframe validator requires an invocation")
    return context.invocation


def _require_dataset(context: FrameValidationContext) -> spec_model.Dataset:
    if context.dataset is None:
        raise TypeError("Declared type validation requires a dataset")
    return context.dataset
