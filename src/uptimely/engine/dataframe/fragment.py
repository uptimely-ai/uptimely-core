"""Dataframe fragments returned by data-producing invocations."""

from __future__ import annotations

import dataclasses
import typing
from collections import abc

from uptimely import execution_plan
from uptimely.spec import functions

from . import backend as backend_module
from . import validation as dataframe_validation

if typing.TYPE_CHECKING:
    from uptimely.engine.runtime import validation as runtime_validation


@dataclasses.dataclass(frozen=True)
class Fragment:
    """Data contributed to a dataset, with its carried dimension keys.

    A fragment may come from a source, another dataset, or a calculation at the
    target grain. Staging loads, validates, and projects its dataframe before merging.
    """

    dataframe: object
    dimensions: tuple[str, ...]
    invocation: execution_plan.Invocation | None = None

    @classmethod
    def stage(
        cls,
        backend: backend_module.DataFrameBackend,
        invocation: execution_plan.Invocation,
        load: abc.Callable[[], object],
        *,
        validator: runtime_validation.ValidationPolicy,
        comparison_frame: object | None = None,
    ) -> Fragment:
        """Load an invocation result and prepare a fragment for physical assembly.

        Args:
            backend: Dataframe operations used to inspect and project the result.
            invocation: Data-producing invocation to stage.
            load: Callable that resolves arguments and executes the invocation.
            validator: Per-run policy for checking the raw result before projection.
            comparison_frame: Current accumulated data for preservation checks.

        Returns:
            A fragment containing only carried keys and declared output columns.

        Raises:
            ValueError: The function kind cannot produce a dataframe fragment or
                validation rejects the invocation result.
        """
        definition = functions.FUNCTION_KINDS.get(invocation.function_kind)
        if definition is None:
            raise ValueError(f"Unknown function kind: {invocation.function_kind}")
        if definition.fragment_dimensions == "not_applicable":
            raise ValueError(
                f"Function kind {invocation.function_kind} does not materialize dataframe results"
            )
        dataframe = load()
        dimensions = tuple(invocation.id_columns)
        if definition.fragment_dimensions == "subset" and backend.is_frame(dataframe):
            columns = set(backend.column_names(dataframe))
            dimensions = tuple(key for key in dimensions if key in columns)
        outputs = [key for key in invocation.output_features if key not in invocation.id_columns]
        validator.validate_fragment(
            dataframe_validation.FrameValidationContext(
                backend,
                dataframe,
                list(dimensions),
                f"Fragment {invocation.function_id}",
                invalid_frame_message=(
                    f"Fragment {invocation.function_id} must return a Polars DataFrame or LazyFrame"
                ),
                invocation=invocation,
                output_features=outputs,
                comparison_frame=comparison_frame,
                column_types=invocation.column_types,
            )
        )
        columns = list(dict.fromkeys([*dimensions, *outputs]))
        return cls(backend.select(dataframe, columns), dimensions, invocation)
