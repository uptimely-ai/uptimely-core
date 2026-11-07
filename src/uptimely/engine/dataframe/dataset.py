"""Physical dataframe accumulation using explicit identifier columns."""

import logging
from collections import abc

from uptimely import plan as execution_plan
from uptimely.library.merge import polars as merge_module
from uptimely.spec import function_kinds as functions

from . import backend as backend_module
from . import fragment as fragment_module

logger = logging.getLogger(__name__)


class Dataset:
    """Own an accumulated dataframe and assemble fragments by identifier columns."""

    def __init__(
        self,
        backend: backend_module.DataFrameBackend,
        id_columns: abc.Sequence[str],
        dataframe: object | None = None,
    ) -> None:
        """Create a physical accumulator with explicit identifier columns."""
        self.backend = backend
        self.id_columns = tuple(id_columns)
        self.dataframe = dataframe
        self.fragments: dict[str, fragment_module.Fragment] = {}

    def validate_accumulated_frame(
        self,
        *,
        description: str = "Accumulated dataset",
        column_types: abc.Mapping[str, str] | None = None,
    ) -> None:
        """Validate the accumulated dataframe's structure, keys, and known types.

        Args:
            description: Name used in validation errors.
            column_types: Declared logical types keyed by column name.

        Raises:
            ValueError: The dataset violates its structural or type contract.
        """
        logger.debug("  Dataset:")
        self._validate_frame_structure(self.dataframe, description)
        self._validate_dimensionless_row_count(self.dataframe, description)
        self._validate_unique_dimension_keys(self.dataframe, description)
        self._validate_declared_types(self.dataframe, column_types)

    def validate_fragment_merge(
        self,
        fragment: fragment_module.Fragment,
        *,
        description: str = "Accumulated profile",
        column_types: abc.Mapping[str, str] | None = None,
        validate: bool = False,
    ) -> None:
        """Check fragment feature collisions and optionally validate this dataset.

        Args:
            fragment: Prepared contribution whose dimension columns may overlap.
            description: Name used if full validation of this dataset fails.
            column_types: Declared logical types keyed by column name.
            validate: Whether to check this dataset's full runtime contract.

        Raises:
            ValueError: The fragment collides with existing features or the dataset
                violates its runtime contract.
        """
        logger.debug("    - checking fragment feature collisions")
        fragment_columns = set(self.backend.column_names(fragment.dataframe))
        existing_columns = set(self.backend.column_names(self.dataframe))
        collisions = sorted((fragment_columns - set(self.id_columns)) & existing_columns)
        if collisions:
            raise ValueError(
                "Fragment feature columns overlap the accumulated profile frame: "
                + ", ".join(collisions)
            )
        if validate:
            self.validate_accumulated_frame(
                description=description,
                column_types=column_types,
            )

    def validate_merge_candidate(
        self,
        target: object | None,
        fragment: fragment_module.Fragment,
        *,
        description: str,
        column_types: abc.Mapping[str, str] | None = None,
        validate: bool = False,
    ) -> None:
        """Validate this dataset's candidate merge result before it is published.

        Args:
            target: The previous target dataframe, or ``None`` for initialization.
            fragment: Staged contribution included in the merge.
            description: Name used in validation errors.
            column_types: Declared logical types keyed by column name.
            validate: Whether to check key uniqueness and declared types.

        Raises:
            ValueError: The result has an invalid dataframe contract.
        """
        self._validate_frame_structure(self.dataframe, description)
        expected_columns = list(
            dict.fromkeys(
                [
                    *(self.backend.column_names(target) if target is not None else []),
                    *self.backend.column_names(fragment.dataframe),
                ]
            )
        )
        self._validate_merge_candidate_columns(
            self.dataframe,
            expected_columns,
            description,
        )
        if validate:
            self._validate_dimensionless_row_count(self.dataframe, description)
            self._validate_unique_dimension_keys(self.dataframe, description)
            self._validate_declared_types(self.dataframe, column_types)

    def validate_vectorized_result(
        self,
        frame: object,
        invocation: execution_plan.Invocation,
        comparison_frame: object,
        *,
        preserve_data: bool = False,
    ) -> list[str]:
        """Validate a vectorized result against its complete accumulated target.

        Args:
            frame: Candidate dataframe returned by the vectorize invocation.
            invocation: Invocation whose output and preservation contracts apply.
            comparison_frame: Original target used for collision and preservation checks.
            preserve_data: Whether to compare existing values, row order, and types.

        Returns:
            Declared output feature names, excluding identifier columns.

        Raises:
            ValueError: The result omits, replaces, or adds undeclared columns, or
                changes existing data when preservation checking is enabled.
        """
        description = f"Vectorize result {invocation.function_id}"
        logger.debug("  Enriched target frame:")
        self._validate_frame_structure(frame, description)
        output_features = [
            output for output in invocation.output_features if output not in self.id_columns
        ]
        logger.debug("    - checking declared vectorize outputs")
        columns = set(self.backend.column_names(frame))
        missing_outputs = sorted(set(output_features) - columns)
        if missing_outputs:
            raise ValueError(
                f"Vectorize operator {invocation.operator_id} is missing output columns: "
                + ", ".join(missing_outputs)
            )

        logger.debug("    - checking vectorize output collisions")
        existing_columns = set(self.backend.column_names(comparison_frame))
        existing_features = existing_columns - set(self.id_columns)
        collisions = sorted(set(output_features) & existing_features)
        if collisions:
            raise ValueError(
                f"Vectorize operator {invocation.operator_id} cannot replace existing "
                "columns: " + ", ".join(collisions)
            )

        logger.debug("    - checking preservation of existing columns")
        missing_existing = sorted(existing_columns - columns)
        if missing_existing:
            raise ValueError(
                f"Vectorize operator {invocation.operator_id} must preserve existing "
                "columns: " + ", ".join(missing_existing)
            )

        logger.debug("    - checking undeclared added columns")
        allowed_columns = existing_columns | set(output_features)
        unexpected = sorted(columns - allowed_columns)
        if unexpected:
            raise ValueError(
                f"Vectorize operator {invocation.operator_id} returned undeclared columns: "
                + ", ".join(unexpected)
            )

        if preserve_data:
            definition = functions.FUNCTION_KINDS[invocation.function_kind]
            if (
                definition.row_order_relation == "preserve"
                or definition.existing_data_relation == "preserve"
            ):
                logger.debug("    - checking existing values and row order")
                existing_names = self.backend.column_names(comparison_frame)
                if not self.backend.same_data(comparison_frame, frame, existing_names):
                    raise ValueError(
                        f"Vectorize operator {invocation.operator_id} must preserve existing "
                        "column values and row order"
                    )
            logger.debug("    - checking types of target keys and outputs")
            self._validate_column_types(
                frame,
                invocation.column_types,
                [*self.id_columns, *output_features],
            )
        return output_features

    def _validate_frame_structure(self, frame: object, description: str) -> None:
        logger.debug("    - checking dataframe type")
        if not self.backend.is_frame(frame):
            raise ValueError(f"{description} must be a Polars DataFrame or LazyFrame")
        logger.debug("    - checking required dimension columns")
        missing = sorted(set(self.id_columns) - set(self.backend.column_names(frame)))
        if missing:
            raise ValueError(f"{description} is missing dimension columns: " + ", ".join(missing))

    def _validate_dimensionless_row_count(self, frame: object, description: str) -> None:
        if self.id_columns:
            logger.debug("    - skipping dimensionless row count (data has dimensions)")
            return
        logger.debug("    - checking dimensionless row count")
        if self.backend.row_count(frame) > 1:
            raise ValueError(
                f"{description} contains duplicate dimension keys "
                "(dimensionless profile frames allow at most one row)"
            )

    def _validate_unique_dimension_keys(self, frame: object, description: str) -> None:
        if not self.id_columns:
            logger.debug("    - skipping dimension-key uniqueness (no dimensions)")
            return
        logger.debug("    - checking dimension-key uniqueness")
        keys = self.backend.select(frame, self.id_columns)
        if self.backend.is_duplicated(keys):
            raise ValueError(f"{description} contains duplicate dimension keys")

    def _validate_declared_types(
        self, frame: object, column_types: abc.Mapping[str, str] | None
    ) -> None:
        logger.debug("    - checking types of present columns")
        columns = set(self.backend.column_names(frame))
        types = {
            name: expected for name, expected in (column_types or {}).items() if name in columns
        }
        logger.debug("      Declared types: %s", types)
        self.backend.validate_types(frame, types)

    def _validate_column_types(
        self,
        frame: object,
        column_types: abc.Mapping[str, str],
        columns: abc.Sequence[str],
    ) -> None:
        types = {name: column_types[name] for name in columns if name in column_types}
        logger.debug("      Declared types: %s", types)
        self.backend.validate_types(frame, types)

    def _validate_merge_candidate_columns(
        self, frame: object, expected_columns: list[str], description: str
    ) -> None:
        actual_columns = set(self.backend.column_names(frame))
        missing = sorted(set(expected_columns) - actual_columns)
        if missing:
            raise ValueError(f"{description} is missing required columns: " + ", ".join(missing))
        unexpected = sorted(actual_columns - set(expected_columns))
        if unexpected:
            raise ValueError(f"{description} contains undeclared columns: " + ", ".join(unexpected))

    def merge(
        self,
        fragment: fragment_module.Fragment,
        *,
        fragment_id: str | None = None,
        join_cardinality: str = "m:m",
        broadcast_cardinality: str = "m:m",
    ) -> fragment_module.Fragment:
        """Merge a prepared contribution, optionally retaining it under an explicit ID.

        Equal identifier sets use a full join, preserving either observation scope.
        A strict subset uses a left join, broadcasting over the existing scope;
        an empty subset uses a cross join. State changes only after assembly succeeds.

        Args:
            fragment: Prepared data and its carried identifier columns.
            fragment_id: Optional key under which to retain the merged fragment.
            join_cardinality: Backend cardinality check for a full join.
            broadcast_cardinality: Backend cardinality check for a subset-key left join.

        Returns:
            The merged fragment, unchanged.

        Raises:
            ValueError: Identifier columns are incompatible or a broadcast has no target.
        """
        merged = merge_module.merge_by_grain(
            self.dataframe,
            fragment.dataframe,
            self.id_columns,
            fragment.dimensions,
            join_cardinality=join_cardinality,
            broadcast_cardinality=broadcast_cardinality,
        )
        self.dataframe = merged
        if fragment_id is not None:
            self.fragments[fragment_id] = fragment
        return fragment
