"""Dataframe fragments returned by data-producing invocations."""

from __future__ import annotations

import dataclasses
import logging
from collections import abc

from uptimely import plan as plan_module
from uptimely.spec import function_kinds

from . import backend as backend_module

logger = logging.getLogger(__name__)


def _log_validation(invocation: plan_module.Invocation, message: str, *args: object) -> None:
    """Log a fragment check with the identity of its producing invocation."""
    logger.debug(
        message + " from operator %s, function %s, invocation %s, profile %s",
        *args,
        invocation.operator_id,
        invocation.function_id,
        invocation.id,
        invocation.profile_id,
    )


@dataclasses.dataclass(frozen=True)
class Fragment:
    """Data contributed to a dataset, with explicit grain and merge identifiers.

    A fragment may come from a source, another dataset, or a calculation at the
    target grain. Staging loads, validates, and projects its dataframe before merging.
    Dimensions define uniqueness; identifiers also include other carried resolution
    keys. Invocation metadata is retained only as provenance.
    """

    dataframe: object
    dimensions: tuple[str, ...]
    invocation: plan_module.Invocation | None = None
    identifiers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Always include carried grain keys among the fragment identifiers."""
        object.__setattr__(
            self, "identifiers", tuple(dict.fromkeys([*self.dimensions, *self.identifiers]))
        )

    @classmethod
    def stage(
        cls,
        backend: backend_module.DataFrameBackend,
        invocation: plan_module.Invocation,
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
        definition = function_kinds.FUNCTION_KINDS.get(invocation.function_kind)
        if definition is None:
            raise ValueError(f"Unknown function kind: {invocation.function_kind}")
        if not definition.produces_fragment:
            raise ValueError(
                f"Function kind {invocation.function_kind} does not produce dataframe fragments"
            )
        dataframe = load()
        if not backend.is_frame(dataframe):
            raise ValueError(
                f"Fragment {invocation.function_id} must return a Polars DataFrame or LazyFrame"
            )
        columns = set(backend.column_names(dataframe))
        dimensions = tuple(invocation.id_columns)
        keys = dict.fromkeys([*dimensions, *invocation.identifier_columns])
        identifiers = tuple(key for key in keys if key in columns)
        if definition.fragment_dimensions == "subset" and not set(dimensions).issubset(columns):
            dimensions = identifiers
        outputs = [key for key in invocation.output_features if key not in invocation.id_columns]
        for key in identifiers:
            if key not in dimensions and key not in outputs:
                outputs.append(key)
        cls(dataframe, dimensions, invocation, identifiers).validate_invocation_result(
            backend,
            invocation,
            output_features=outputs,
            comparison_frame=comparison_frame,
            validate_content=validate,
        )
        columns = list(dict.fromkeys([*dimensions, *outputs]))
        return cls(backend.select(dataframe, columns), dimensions, invocation, identifiers)

    def validate_invocation_result(
        self,
        backend: backend_module.DataFrameBackend,
        invocation: plan_module.Invocation,
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
        _log_validation(invocation, "Check fragment dataframe type")
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
        definition = function_kinds.FUNCTION_KINDS.get(invocation.function_kind)
        if definition is None:
            raise ValueError(f"Unknown function kind: {invocation.function_kind}")
        if definition.row_count_relation == "same":
            _log_validation(invocation, "Check fragment row-count preservation")
            if comparison_frame is None or backend.row_count(comparison_frame) != backend.row_count(
                self.dataframe
            ):
                raise ValueError(
                    f"{invocation.function_kind.capitalize()} operator "
                    f"{invocation.operator_id} "
                    "must preserve the accumulated profile row count"
                )
        else:
            _log_validation(invocation, "Skipping fragment row-count preservation (not required)")

        self._validate_unique_dimension_keys(backend, invocation)
        self._validate_output_columns(backend, invocation, expected_outputs)
        _log_validation(invocation, "Check fragment dimension and output types")
        self._validate_column_types(
            backend,
            invocation,
            [*self.dimensions, *expected_outputs],
        )
        if definition.key_relation == "identical":
            _log_validation(
                invocation,
                "Check fragment dimension-key preservation for columns %s",
                self.dimensions,
            )
            if comparison_frame is None or not backend.same_keys(
                comparison_frame, self.dataframe, self.dimensions
            ):
                raise ValueError(
                    f"{invocation.function_kind.capitalize()} operator "
                    f"{invocation.operator_id} "
                    "must preserve the profile grain keys"
                )
        else:
            _log_validation(
                invocation, "Skipping fragment dimension-key preservation (not required)"
            )

    def _validate_dimension_columns(
        self,
        backend: backend_module.DataFrameBackend,
        invocation: plan_module.Invocation,
    ) -> None:
        _log_validation(invocation, "Check fragment required dimension columns %s", self.dimensions)
        missing = sorted(set(self.dimensions) - set(backend.column_names(self.dataframe)))
        if missing:
            raise ValueError(
                f"Fragment {invocation.function_id} is missing dimension columns: "
                + ", ".join(missing)
            )

    def _validate_dimensionless_row_count(
        self, backend: backend_module.DataFrameBackend, invocation: plan_module.Invocation
    ) -> None:
        if self.dimensions:
            _log_validation(
                invocation, "Skipping fragment dimensionless row count (data has dimensions)"
            )
            return
        _log_validation(invocation, "Check fragment dimensionless row count is at most one")
        if backend.row_count(self.dataframe) > 1:
            raise ValueError(
                f"Fragment {invocation.function_id} contains duplicate dimension keys "
                "(dimensionless profile frames allow at most one row)"
            )

    def _validate_unique_dimension_keys(
        self,
        backend: backend_module.DataFrameBackend,
        invocation: plan_module.Invocation,
    ) -> None:
        if not self.dimensions:
            _log_validation(
                invocation, "Skipping fragment dimension-key uniqueness (no dimensions)"
            )
            return
        _log_validation(
            invocation, "Check fragment dimension-key uniqueness for columns %s", self.dimensions
        )
        keys = backend.select(self.dataframe, self.dimensions)
        if backend.is_duplicated(keys):
            raise ValueError(f"Fragment {invocation.function_id} contains duplicate dimension keys")

    def _validate_output_columns(
        self,
        backend: backend_module.DataFrameBackend,
        invocation: plan_module.Invocation,
        output_features: abc.Sequence[str],
    ) -> None:
        _log_validation(
            invocation, "Check fragment declared output columns %s", list(output_features)
        )
        missing = sorted(set(output_features) - set(backend.column_names(self.dataframe)))
        if missing:
            raise ValueError(
                f"Operator {invocation.operator_id} is missing output columns: "
                + ", ".join(missing)
            )

    def _validate_column_types(
        self,
        backend: backend_module.DataFrameBackend,
        invocation: plan_module.Invocation,
        columns: abc.Sequence[str],
    ) -> None:
        types = {
            name: invocation.column_types[name]
            for name in columns
            if name in invocation.column_types
        }
        _log_validation(invocation, "Check fragment declared column types %s", types)
        backend.validate_types(self.dataframe, types)
