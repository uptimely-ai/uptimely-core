"""Validate runtime dataframe inputs, results, and structural contracts."""

from __future__ import annotations

import collections.abc
import dataclasses
import graphlib

from uptimely import execution_plan
from uptimely.engine.dataframe import backend as backend_module
from uptimely.spec import functions


@dataclasses.dataclass(frozen=True)
class FrameValidationContext:
    """One dataframe and its structural validation requirements."""

    backend: backend_module.DataFrameBackend
    frame: object
    dimensions: list[str]
    description: str
    invalid_frame_message: str | None = None
    invocation: execution_plan.Invocation | None = None
    output_features: list[str] | None = None
    declared_type_columns: list[str] | None = None
    comparison_frame: object | None = None
    column_types: dict[str, str] = dataclasses.field(default_factory=dict)

    @property
    def columns(self) -> set[str]:
        """Return the current frame's column names."""
        return set(self.backend.column_names(self.frame))

    @property
    def effective_output_features(self) -> list[str]:
        """Return explicitly overridden outputs, or the invocation's declared outputs."""
        return (
            self.output_features
            if self.output_features is not None
            else _require_invocation(self).output_features
        )


type DataFrameValidationContext = FrameValidationContext
type Validator = collections.abc.Callable[[DataFrameValidationContext], None]


def validate_feature_collisions(
    backend: backend_module.DataFrameBackend,
    dataframe: object,
    fragment: object,
    dimensions: list[str],
) -> None:
    """Reject output feature names already present in the accumulated dataset."""
    dataframe_columns = set(backend.column_names(dataframe))
    fragment_columns = set(backend.column_names(fragment))
    collisions = sorted((fragment_columns - set(dimensions)) & dataframe_columns)
    if collisions:
        raise ValueError(
            "Fragment feature columns overlap the accumulated dataset: " + ", ".join(collisions)
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
    missing = sorted(set(frame_context.dimensions) - frame_context.columns)
    if missing:
        raise ValueError(
            f"{frame_context.description} is missing dimension columns: " + ", ".join(missing)
        )


def validate_unique_dimension_keys(context: DataFrameValidationContext) -> None:
    """Reject duplicate observation keys."""
    frame_context = _require_frame_context(context)
    if not frame_context.dimensions:
        return
    keys = frame_context.backend.select(frame_context.frame, frame_context.dimensions)
    if frame_context.backend.is_duplicated(keys):
        raise ValueError(f"{frame_context.description} contains duplicate dimension keys")


def validate_row_count(context: DataFrameValidationContext) -> None:
    """Enforce dimensionless and kind-specific row-count contracts."""
    frame_context = _require_frame_context(context)
    if not frame_context.dimensions and frame_context.backend.row_count(frame_context.frame) > 1:
        raise ValueError(
            f"{frame_context.description} contains duplicate dimension keys "
            "(dimensionless datasets allow at most one row)"
        )

    if frame_context.invocation is None:
        return
    if _function_definition(frame_context).row_count_relation != "same":
        return
    comparison_frame = frame_context.comparison_frame
    if comparison_frame is None:
        invocation = _require_invocation(frame_context)
        raise ValueError(
            f"{invocation.function_kind.capitalize()} action {invocation.mapping_id} "
            "must preserve the accumulated dataset row count"
        )
    if frame_context.backend.row_count(comparison_frame) != frame_context.backend.row_count(
        frame_context.frame
    ):
        invocation = _require_invocation(frame_context)
        raise ValueError(
            f"{invocation.function_kind.capitalize()} action {invocation.mapping_id} "
            "must preserve the accumulated dataset row count"
        )


def validate_output_columns(context: DataFrameValidationContext) -> None:
    """Require every declared action output in the returned fragment."""
    frame_context = _require_frame_context(context)
    invocation = _require_invocation(frame_context)
    missing = sorted(set(frame_context.effective_output_features) - frame_context.columns)
    if missing:
        raise ValueError(
            f"Action {invocation.mapping_id} is missing output columns: " + ", ".join(missing)
        )


def validate_fragment_declared_types(context: DataFrameValidationContext) -> None:
    """Check declared logical types for a returned fragment's keys and outputs."""
    frame_context = _require_frame_context(context)
    _validate_declared_types(
        frame_context,
        [*frame_context.dimensions, *frame_context.effective_output_features],
    )


def validate_dataset_declared_types(context: DataFrameValidationContext) -> None:
    """Check declared logical types for columns already present in an accumulated dataset."""
    frame_context = _require_frame_context(context)
    columns = frame_context.declared_type_columns
    if columns is None:
        raise TypeError("Dataset type validation requires declared type columns")
    _validate_declared_types(frame_context, columns)


def validate_key_coverage(context: DataFrameValidationContext) -> None:
    """Enforce the function kind's key-identity contract against its reference frame."""
    frame_context = _require_frame_context(context)
    invocation = _require_invocation(frame_context)
    if _function_definition(frame_context).key_relation != "identical":
        return
    dataframe = frame_context.comparison_frame
    if dataframe is None or not frame_context.backend.same_keys(
        dataframe, frame_context.frame, frame_context.dimensions
    ):
        raise ValueError(
            f"{invocation.function_kind.capitalize()} action {invocation.mapping_id} "
            "must preserve the dataset dimension keys"
        )


DATAFRAME_VALIDATION_DEPENDENCIES: dict[Validator, tuple[Validator, ...]] = {
    validate_frame_type: (),
    validate_dimension_columns: (validate_frame_type,),
    validate_row_count: (validate_dimension_columns,),
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


def validate_frame_structure(
    backend: backend_module.DataFrameBackend,
    frame: object,
    dimensions: list[str],
    description: str,
    invalid_frame_message: str | None = None,
) -> None:
    """Validate frame type, dimension columns, row count, and key uniqueness."""
    validate_dataframes(
        FrameValidationContext(
            backend,
            frame,
            dimensions,
            description,
            invalid_frame_message,
        ),
        (
            validate_frame_type,
            validate_dimension_columns,
            validate_row_count,
            validate_unique_dimension_keys,
        ),
    )


def validate_fragment(context: FrameValidationContext) -> None:
    """Validate a returned fragment against its declared schema and kind contract."""
    validate_dataframes(
        context,
        (
            validate_frame_type,
            validate_dimension_columns,
            validate_row_count,
            validate_unique_dimension_keys,
            validate_output_columns,
            validate_fragment_declared_types,
            validate_key_coverage,
        ),
    )


def _validate_declared_types(
    context: FrameValidationContext,
    columns: list[str],
) -> None:
    """Validate logical types declared for selected dataset columns."""
    types = {name: context.column_types[name] for name in columns if name in context.column_types}
    context.backend.validate_types(context.frame, types)


def _function_definition(context: FrameValidationContext) -> functions.FunctionKind:
    """Resolve the kind contract for a materialized invocation result."""
    invocation = _require_invocation(context)
    definition = functions.FUNCTION_KINDS.get(invocation.function_kind)
    if definition is None:
        raise ValueError(f"Unknown function kind: {invocation.function_kind}")
    return definition


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
