"""Validate raw fragments and accumulated main frames at runtime boundaries."""

from __future__ import annotations

import dataclasses
import logging

from uptimely import execution_plan
from uptimely.spec import functions

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

    def _validate_frame_type(self) -> None:
        """Require a dataframe before inspecting its schema."""
        logger.debug("    - checking dataframe type")
        if not self.backend.is_frame(self.frame):
            raise ValueError(
                self.invalid_frame_message
                or f"{self.description} must be a Polars DataFrame or LazyFrame"
            )

    def _validate_dimension_columns(self) -> None:
        """Require all carried dimension columns."""
        logger.debug("    - checking required dimension columns")
        missing = sorted(set(self.dimensions) - self.columns)
        if missing:
            raise ValueError(
                f"{self.description} is missing dimension columns: " + ", ".join(missing)
            )

    def _validate_dimensionless_row_count(self) -> None:
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

    def _validate_unique_dimension_keys(self) -> None:
        """Reject duplicate observation keys."""
        if not self.dimensions:
            logger.debug("    - skipping dimension-key uniqueness (no dimensions)")
            return
        logger.debug("    - checking dimension-key uniqueness")
        keys = self.backend.select(self.frame, self.dimensions)
        if self.backend.is_duplicated(keys):
            raise ValueError(f"{self.description} contains duplicate dimension keys")

    def _validate_column_types(self, columns: list[str]) -> None:
        """Validate logical types declared for selected columns."""
        types = {name: self.column_types[name] for name in columns if name in self.column_types}
        logger.debug("      Declared types: %s", types)
        self.backend.validate_types(self.frame, types)


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

    def validate(self) -> None:
        """Check structure, outputs, types, and function-kind preservation rules.

        Raises:
            ValueError: The fragment violates its declared dataframe contract.
        """
        logger.debug("  Fragment:")
        self._validate_frame_type()
        self._validate_dimension_columns()
        self._validate_dimensionless_row_count()
        self._validate_row_count()
        self._validate_unique_dimension_keys()
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
                f"{self.invocation.function_kind.capitalize()} action {self.invocation.mapping_id} "
                "must preserve the accumulated profile row count"
            )

    def _validate_output_columns(self) -> None:
        """Require every declared action output in the raw result."""
        logger.debug("    - checking declared output columns")
        missing = sorted(set(self.effective_output_features) - self.columns)
        if missing:
            raise ValueError(
                f"Action {self.invocation.mapping_id} is missing output columns: "
                + ", ".join(missing)
            )

    def _validate_declared_types(self) -> None:
        """Check logical types of carried dimensions and declared outputs."""
        logger.debug("    - checking dimension and output types")
        self._validate_column_types([*self.dimensions, *self.effective_output_features])

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
                f"{self.invocation.function_kind.capitalize()} action {self.invocation.mapping_id} "
                "must preserve the profile grain keys"
            )

    def _function_definition(self) -> functions.FunctionKind:
        """Resolve the invocation's declarative function-kind contract."""
        definition = functions.FUNCTION_KINDS.get(self.invocation.function_kind)
        if definition is None:
            raise ValueError(f"Unknown function kind: {self.invocation.function_kind}")
        return definition


@dataclasses.dataclass(frozen=True)
class MainFrameValidator(_FrameValidator):
    """Validate accumulated frame structure and types of present columns."""

    def validate(self) -> None:
        """Check structure before inspecting declared types of existing columns.

        Raises:
            ValueError: The main frame violates its structural or type contract.
        """
        logger.debug("  Main frame:")
        self._validate_frame_type()
        self._validate_dimension_columns()
        self._validate_dimensionless_row_count()
        self._validate_unique_dimension_keys()
        self._validate_declared_types()

    def _validate_declared_types(self) -> None:
        """Check only declared columns already present in the accumulated frame."""
        logger.debug("    - checking types of present columns")
        columns = self.columns
        self._validate_column_types([name for name in self.column_types if name in columns])

    def validate_merge(self, fragment: object) -> None:
        """Check feature collisions before joining a prepared fragment.

        Args:
            fragment: Prepared dataframe whose dimension columns may overlap.

        Raises:
            ValueError: A fragment feature already exists in the main frame.
        """
        self._validate_feature_collisions(fragment)

    def _validate_feature_collisions(self, fragment: object) -> None:
        """Reject output feature names already present in the accumulated profile frame."""
        logger.debug("    - checking fragment feature collisions")
        fragment_columns = set(self.backend.column_names(fragment))
        collisions = sorted((fragment_columns - set(self.dimensions)) & self.columns)
        if collisions:
            raise ValueError(
                "Fragment feature columns overlap the accumulated profile frame: "
                + ", ".join(collisions)
            )
