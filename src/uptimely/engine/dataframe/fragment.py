"""Dataframe fragments returned by data-producing invocations."""

from __future__ import annotations

import dataclasses
import logging
from collections import abc

from uptimely import plan as execution_plan
from uptimely.spec import function_kinds as functions

from . import backend as backend_module

logger = logging.getLogger(__name__)


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
        validate: bool = False,
        comparison_frame: object | None = None,
    ) -> Fragment:
        """Load an invocation result and prepare a fragment for physical assembly.

        Args:
            backend: Dataframe operations used to inspect and project the result.
            invocation: Data-producing invocation to stage.
            load: Callable that resolves arguments and executes the invocation.
            validate: Whether to check the raw result before projection.
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
        if not definition.produces_fragment:
            raise ValueError(
                f"Function kind {invocation.function_kind} does not produce dataframe fragments"
            )
        dataframe = load()
        dimensions = tuple(invocation.id_columns)
        if definition.fragment_dimensions == "subset" and backend.is_frame(dataframe):
            columns = set(backend.column_names(dataframe))
            dimensions = tuple(key for key in dimensions if key in columns)
        outputs = [key for key in invocation.output_features if key not in invocation.id_columns]
        cls(dataframe, dimensions, invocation).validate_invocation_result(
            backend,
            invocation,
            output_features=outputs,
            comparison_frame=comparison_frame,
            validate_content=validate,
        )
        columns = list(dict.fromkeys([*dimensions, *outputs]))
        return cls(backend.select(dataframe, columns), dimensions, invocation)

    def validate_invocation_result(
        self,
        backend: backend_module.DataFrameBackend,
        invocation: execution_plan.Invocation,
        *,
        output_features: abc.Sequence[str] | None = None,
        comparison_frame: object | None = None,
        validate_content: bool = True,
    ) -> None:
        """Validate a raw invocation result before projecting declared outputs.

        Args:
            backend: Dataframe operations used to inspect the result.
            invocation: Invocation whose dataframe contract applies.
            output_features: Output columns to require; defaults to invocation outputs
                excluding its identifier columns.
            comparison_frame: Accumulated data used by preservation contracts.
            validate_content: Whether to check row/key preservation, uniqueness,
                and declared column types.

        Raises:
            ValueError: The result violates its dataframe contract.
        """
        logger.debug("  Fragment:")
        logger.debug("    - checking dataframe type")
        if not backend.is_frame(self.dataframe):
            raise ValueError(
                f"Fragment {invocation.function_id} must return a Polars DataFrame or LazyFrame"
            )
        self._validate_dimension_columns(backend, invocation)
        expected_outputs = (
            list(output_features)
            if output_features is not None
            else [
                output
                for output in invocation.output_features
                if output not in invocation.id_columns
            ]
        )
        if not validate_content:
            self._validate_output_columns(backend, invocation, expected_outputs)
            return

        self._validate_dimensionless_row_count(backend, invocation)
        definition = functions.FUNCTION_KINDS.get(invocation.function_kind)
        if definition is None:
            raise ValueError(f"Unknown function kind: {invocation.function_kind}")
        if definition.row_count_relation == "same":
            logger.debug("    - checking row-count preservation")
            if comparison_frame is None or backend.row_count(comparison_frame) != backend.row_count(
                self.dataframe
            ):
                raise ValueError(
                    f"{invocation.function_kind.capitalize()} operator "
                    f"{invocation.operator_id} "
                    "must preserve the accumulated profile row count"
                )
        else:
            logger.debug("    - skipping row-count preservation (not required)")

        self._validate_unique_dimension_keys(backend, invocation)
        self._validate_output_columns(backend, invocation, expected_outputs)
        logger.debug("    - checking dimension and output types")
        self._validate_column_types(
            backend,
            invocation,
            [*self.dimensions, *expected_outputs],
        )
        if definition.key_relation == "identical":
            logger.debug("    - checking dimension-key preservation")
            if comparison_frame is None or not backend.same_keys(
                comparison_frame, self.dataframe, self.dimensions
            ):
                raise ValueError(
                    f"{invocation.function_kind.capitalize()} operator "
                    f"{invocation.operator_id} "
                    "must preserve the profile grain keys"
                )
        else:
            logger.debug("    - skipping dimension-key preservation (not required)")

    def _validate_dimension_columns(
        self,
        backend: backend_module.DataFrameBackend,
        invocation: execution_plan.Invocation,
    ) -> None:
        logger.debug("    - checking required dimension columns")
        missing = sorted(set(self.dimensions) - set(backend.column_names(self.dataframe)))
        if missing:
            raise ValueError(
                f"Fragment {invocation.function_id} is missing dimension columns: "
                + ", ".join(missing)
            )

    def _validate_dimensionless_row_count(
        self, backend: backend_module.DataFrameBackend, invocation: execution_plan.Invocation
    ) -> None:
        if self.dimensions:
            logger.debug("    - skipping dimensionless row count (data has dimensions)")
            return
        logger.debug("    - checking dimensionless row count")
        if backend.row_count(self.dataframe) > 1:
            raise ValueError(
                f"Fragment {invocation.function_id} contains duplicate dimension keys "
                "(dimensionless profile frames allow at most one row)"
            )

    def _validate_unique_dimension_keys(
        self,
        backend: backend_module.DataFrameBackend,
        invocation: execution_plan.Invocation,
    ) -> None:
        if not self.dimensions:
            logger.debug("    - skipping dimension-key uniqueness (no dimensions)")
            return
        logger.debug("    - checking dimension-key uniqueness")
        keys = backend.select(self.dataframe, self.dimensions)
        if backend.is_duplicated(keys):
            raise ValueError(f"Fragment {invocation.function_id} contains duplicate dimension keys")

    def _validate_output_columns(
        self,
        backend: backend_module.DataFrameBackend,
        invocation: execution_plan.Invocation,
        output_features: abc.Sequence[str],
    ) -> None:
        logger.debug("    - checking declared output columns")
        missing = sorted(set(output_features) - set(backend.column_names(self.dataframe)))
        if missing:
            raise ValueError(
                f"Operator {invocation.operator_id} is missing output columns: "
                + ", ".join(missing)
            )

    def _validate_column_types(
        self,
        backend: backend_module.DataFrameBackend,
        invocation: execution_plan.Invocation,
        columns: abc.Sequence[str],
    ) -> None:
        types = {
            name: invocation.column_types[name]
            for name in columns
            if name in invocation.column_types
        }
        logger.debug("      Declared types: %s", types)
        backend.validate_types(self.dataframe, types)
