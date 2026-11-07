"""Validate raw fragments and accumulated datasets at runtime boundaries."""

from __future__ import annotations

import dataclasses
import logging

from uptimely import plan as execution_plan
from uptimely.spec import function_kinds as functions

from . import backend as backend_module

logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class _FrameValidator:
    """Share dataframe attributes and atomic structural checks."""

    backend: backend_module.DataFrameBackend
    frame: object
    dimensions: list[str]
    description: str
    invalid_frame_message: str | None = None
    column_types: dict[str, str] = dataclasses.field(default_factory=dict)

    @property
    def columns(self) -> set[str]:
        """Return the current frame's column names."""
        return set(self.backend.column_names(self.frame))

    def validate_frame_type(self) -> None:
        """Require a dataframe before inspecting its schema."""
        logger.debug("    - checking dataframe type")
        if not self.backend.is_frame(self.frame):
            raise ValueError(
                self.invalid_frame_message
                or f"{self.description} must be a Polars DataFrame or LazyFrame"
            )

    def validate_dimension_columns(self) -> None:
        """Require all carried dimension columns."""
        logger.debug("    - checking required dimension columns")
        missing = sorted(set(self.dimensions) - self.columns)
        if missing:
            raise ValueError(
                f"{self.description} is missing dimension columns: " + ", ".join(missing)
            )

    def validate_dimensionless_row_count(self) -> None:
        """Limit a dimensionless dataframe to at most one observation."""
        if self.dimensions:
            logger.debug("    - skipping dimensionless row count (data has dimensions)")
            return
        logger.debug("    - checking dimensionless row count")
        if self.backend.row_count(self.frame) > 1:
            raise ValueError(
                f"{self.description} contains duplicate dimension keys "
                "(dimensionless profile frames allow at most one row)"
            )

    def validate_unique_dimension_keys(self) -> None:
        """Reject duplicate observation keys."""
        if not self.dimensions:
            logger.debug("    - skipping dimension-key uniqueness (no dimensions)")
            return
        logger.debug("    - checking dimension-key uniqueness")
        keys = self.backend.select(self.frame, self.dimensions)
        if self.backend.is_duplicated(keys):
            raise ValueError(f"{self.description} contains duplicate dimension keys")

    def validate_column_types(self, columns: list[str]) -> None:
        """Validate logical types declared for selected columns."""
        types = {name: self.column_types[name] for name in columns if name in self.column_types}
        logger.debug("      Declared types: %s", types)
        self.backend.validate_types(self.frame, types)

    def validate(self) -> None:
        """Check common dataframe requirements before specialized validation.

        Raises:
            ValueError: The frame is not a supported dataframe or lacks dimensions.
        """
        self.validate_frame_type()
        self.validate_dimension_columns()


@dataclasses.dataclass(frozen=True, kw_only=True)
class FragmentValidator(_FrameValidator):
    """Validate a raw invocation result before projecting its declared outputs.

    The invocation is required; output overrides and a reference frame apply only
    to this fragment's contract, not to general dataframe structure.
    """

    invocation: execution_plan.Invocation
    output_features: list[str] | None = None
    comparison_frame: object | None = None

    @property
    def effective_output_features(self) -> list[str]:
        """Return overridden outputs, preserving an explicitly empty override."""
        return (
            self.output_features
            if self.output_features is not None
            else self.invocation.output_features
        )

    def validate(self, *, validate_content: bool = True) -> None:
        """Check structure, outputs, types, and function-kind preservation rules.

        Structural dataframe, dimension, and output checks always run. The
        optional content checks may collect lazy frames and are enabled by default
        for direct validation callers.

        Args:
            validate_content: Whether to check row/key preservation, uniqueness,
                and declared column types.

        Raises:
            ValueError: The fragment violates its declared dataframe contract.
        """
        logger.debug("  Fragment:")
        super().validate()
        if not validate_content:
            self._validate_output_columns()
            return
        self.validate_dimensionless_row_count()
        self._validate_row_count()
        self.validate_unique_dimension_keys()
        self._validate_output_columns()
        self._validate_declared_types()
        self._validate_key_coverage()

    def _validate_row_count(self) -> None:
        """Enforce the function kind's row-count preservation contract."""
        if self._function_definition().row_count_relation != "same":
            logger.debug("    - skipping row-count preservation (not required)")
            return
        logger.debug("    - checking row-count preservation")
        if self.comparison_frame is None or self.backend.row_count(
            self.comparison_frame
        ) != self.backend.row_count(self.frame):
            raise ValueError(
                f"{self.invocation.function_kind.capitalize()} operator "
                f"{self.invocation.operator_id} "
                "must preserve the accumulated profile row count"
            )

    def _validate_output_columns(self) -> None:
        """Require every declared operator output in the raw result."""
        logger.debug("    - checking declared output columns")
        missing = sorted(set(self.effective_output_features) - self.columns)
        if missing:
            raise ValueError(
                f"Operator {self.invocation.operator_id} is missing output columns: "
                + ", ".join(missing)
            )

    def _validate_declared_types(self) -> None:
        """Check logical types of carried dimensions and declared outputs."""
        logger.debug("    - checking dimension and output types")
        self.validate_column_types([*self.dimensions, *self.effective_output_features])

    def _validate_key_coverage(self) -> None:
        """Enforce the function kind's key-identity contract."""
        if self._function_definition().key_relation != "identical":
            logger.debug("    - skipping dimension-key preservation (not required)")
            return
        logger.debug("    - checking dimension-key preservation")
        if self.comparison_frame is None or not self.backend.same_keys(
            self.comparison_frame, self.frame, self.dimensions
        ):
            raise ValueError(
                f"{self.invocation.function_kind.capitalize()} operator "
                f"{self.invocation.operator_id} "
                "must preserve the profile grain keys"
            )

    def _function_definition(self) -> functions.FunctionKind:
        """Resolve the invocation's declarative function-kind contract."""
        definition = functions.FUNCTION_KINDS.get(self.invocation.function_kind)
        if definition is None:
            raise ValueError(f"Unknown function kind: {self.invocation.function_kind}")
        return definition


@dataclasses.dataclass(frozen=True, kw_only=True)
class ColumnsValidator(_FrameValidator):
    """Validate a vectorize result against its complete accumulated target."""

    invocation: execution_plan.Invocation
    comparison_frame: object

    @property
    def output_features(self) -> list[str]:
        """Return declared outputs excluding target grain keys."""
        return [
            output
            for output in self.invocation.output_features
            if output not in self.invocation.id_columns
        ]

    def validate(self, *, preserve_data: bool = False) -> None:
        """Check required frame structure and optionally compare original row data.

        Args:
            preserve_data: Whether to execute lazy queries and compare all existing
                columns, values, and row order with the accumulated target.

        Raises:
            ValueError: The result omits, replaces, or adds undeclared columns, or
                changes existing data when preservation checking is enabled.
        """
        logger.debug("  Enriched target frame:")
        super().validate()
        self._validate_declared_outputs()
        self._validate_output_collisions()
        self._validate_existing_columns()
        self._validate_added_columns()
        if preserve_data:
            definition = functions.FUNCTION_KINDS[self.invocation.function_kind]
            if (
                definition.row_order_relation == "preserve"
                or definition.existing_data_relation == "preserve"
            ):
                self._validate_preserved_data()
            self._validate_declared_types()

    def _validate_declared_outputs(self) -> None:
        """Require every declared output column in the result."""
        logger.debug("    - checking declared vectorize outputs")
        missing = sorted(set(self.output_features) - self.columns)
        if missing:
            raise ValueError(
                f"Vectorize operator {self.invocation.operator_id} is missing output columns: "
                + ", ".join(missing)
            )

    def _validate_output_collisions(self) -> None:
        """Reject outputs that replace features already present in the target."""
        logger.debug("    - checking vectorize output collisions")
        existing_features = set(self.backend.column_names(self.comparison_frame)) - set(
            self.dimensions
        )
        collisions = sorted(set(self.output_features) & existing_features)
        if collisions:
            raise ValueError(
                f"Vectorize operator {self.invocation.operator_id} cannot replace existing "
                "columns: " + ", ".join(collisions)
            )

    def _validate_existing_columns(self) -> None:
        """Require all columns from the accumulated target in the result."""
        logger.debug("    - checking preservation of existing columns")
        existing = self.backend.column_names(self.comparison_frame)
        missing = sorted(set(existing) - self.columns)
        if missing:
            raise ValueError(
                f"Vectorize operator {self.invocation.operator_id} must preserve existing "
                "columns: " + ", ".join(missing)
            )

    def _validate_added_columns(self) -> None:
        """Reject result columns that are neither existing nor declared outputs."""
        logger.debug("    - checking undeclared added columns")
        existing = set(self.backend.column_names(self.comparison_frame))
        allowed = existing | set(self.output_features)
        unexpected = sorted(self.columns - allowed)
        if unexpected:
            raise ValueError(
                f"Vectorize operator {self.invocation.operator_id} returned undeclared columns: "
                + ", ".join(unexpected)
            )

    def _validate_preserved_data(self) -> None:
        """Require unchanged existing values and their original row order."""
        logger.debug("    - checking existing values and row order")
        columns = self.backend.column_names(self.comparison_frame)
        if not self.backend.same_data(self.comparison_frame, self.frame, columns):
            raise ValueError(
                f"Vectorize operator {self.invocation.operator_id} must preserve existing "
                "column values and row order"
            )

    def _validate_declared_types(self) -> None:
        """Check logical types of target keys and newly produced feature columns."""
        self.validate_column_types([*self.dimensions, *self.output_features])


@dataclasses.dataclass(frozen=True)
class DatasetValidator(_FrameValidator):
    """Validate accumulated frame structure and types of present columns."""

    def validate(self) -> None:
        """Check structure before inspecting declared types of existing columns.

        Raises:
            ValueError: The dataset violates its structural or type contract.
        """
        logger.debug("  Main frame:")
        super().validate()
        self.validate_dimensionless_row_count()
        self.validate_unique_dimension_keys()
        self.validate_declared_types()

    def validate_declared_types(self) -> None:
        """Check only declared columns already present in the accumulated frame."""
        logger.debug("    - checking types of present columns")
        columns = self.columns
        types = {name: self.column_types[name] for name in self.column_types if name in columns}
        logger.debug("      Declared types: %s", types)
        self.backend.validate_types(self.frame, types)

    def validate_merge(self, fragment: object, *, validate: bool = False) -> None:
        """Check a merge input's collisions and optionally validate its target.

        Args:
            fragment: Prepared dataframe whose dimension columns may overlap.
            validate: Whether to check the current frame's full runtime contract.

        Raises:
            ValueError: The fragment collides with existing features or the target
                violates its runtime contract.
        """
        logger.debug("    - checking fragment feature collisions")
        fragment_columns = set(self.backend.column_names(fragment))
        collisions = sorted((fragment_columns - set(self.dimensions)) & self.columns)
        if collisions:
            raise ValueError(
                "Fragment feature columns overlap the accumulated profile frame: "
                + ", ".join(collisions)
            )
        if validate:
            self.validate()

    def validate_merge_result(
        self,
        target: object | None,
        fragment: object,
        *,
        validate: bool = False,
    ) -> None:
        """Validate a merge result against its complete target schema.

        Args:
            target: The previous target dataframe, or ``None`` for initialization.
            fragment: The staged fragment being merged.
            validate: Whether to check declared types and key uniqueness.

        Raises:
            ValueError: The result has an invalid dataframe contract.
        """
        super().validate()
        expected_columns = list(
            dict.fromkeys(
                [
                    *(self.backend.column_names(target) if target is not None else []),
                    *self.backend.column_names(fragment),
                ]
            )
        )
        self._validate_merge_result_columns(expected_columns)
        if validate:
            self.validate_dimensionless_row_count()
            self.validate_unique_dimension_keys()
            self.validate_declared_types()

    def _validate_merge_result_columns(self, expected_columns: list[str]) -> None:
        """Require the result to contain exactly the expected target columns."""
        actual_columns = self.columns
        missing = sorted(set(expected_columns) - actual_columns)
        if missing:
            raise ValueError(
                f"{self.description} is missing required columns: " + ", ".join(missing)
            )
        unexpected = sorted(actual_columns - set(expected_columns))
        if unexpected:
            raise ValueError(
                f"{self.description} contains undeclared columns: " + ", ".join(unexpected)
            )
