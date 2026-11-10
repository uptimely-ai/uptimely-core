"""Physical dataframe accumulation using explicit identifier columns."""

import logging
from collections import abc

from . import backend as backend_module
from . import fragment as fragment_module
from . import merge as merge_module

logger = logging.getLogger(__name__)


class Dataset:
    """Own accumulated data, retained fragments, and the dataset's grain contract."""

    def __init__(
        self,
        backend: backend_module.DataFrameBackend,
        identifiers: abc.Sequence[str],
        dataframe: object | None = None,
        *,
        relations: abc.Sequence[str] = (),
    ) -> None:
        """Create a physical accumulator with explicit identifier columns."""
        self.backend = backend
        self.identifiers = tuple(identifiers)
        self.relations = tuple(
            dict.fromkeys(column for column in relations if column not in self.identifiers)
        )
        self.dataframe = dataframe
        self.fragments: dict[str, fragment_module.Fragment] = {}

    @property
    def keys(self) -> tuple[str, ...]:
        """Return this dataset's identifiers and relations together."""
        return (*self.identifiers, *self.relations)

    def validate_accumulated_frame(
        self,
        *,
        description: str = "Accumulated dataset",
        column_types: abc.Mapping[str, str] | None = None,
    ) -> None:
        """Validate the accumulated dataframe's structure, keys, and known types.

        Args:
            description: Dataset identity used in validation logs and errors.
            column_types: Declared logical types keyed by column name.

        Raises:
            ValueError: The dataset violates its structural or type contract.
        """
        self.validate_frame(
            self.dataframe,
            description=description,
            column_types=column_types,
            validate_content=True,
        )

    def validate_frame(
        self,
        frame: object,
        *,
        description: str = "Dataset",
        column_types: abc.Mapping[str, str] | None = None,
        validate_content: bool = False,
    ) -> None:
        """Check a frame against this dataset's grain and declared types.

        Args:
            frame: Accumulated or candidate dataframe to validate.
            description: Identity used in validation logs and errors.
            column_types: Declared logical types keyed by column name.
            validate_content: Whether to check key uniqueness and declared types.

        Raises:
            ValueError: The frame violates the dataset contract.
        """
        self._validate_frame_structure(frame, description)
        if validate_content:
            self._validate_dimensionless_row_count(frame, description)
            self._validate_unique_identifiers(frame, description)
            self._validate_declared_types(frame, column_types, description)

    def _validate_frame_structure(self, frame: object, description: str) -> None:
        logger.debug("Check dataset dataframe type for %s", description)
        if not self.backend.is_frame(frame):
            raise ValueError(f"{description} must be a Polars DataFrame or LazyFrame")
        logger.debug(
            "Check dataset required identifier columns %s for %s", self.identifiers, description
        )
        missing = sorted(set(self.identifiers) - set(self.backend.column_names(frame)))
        if missing:
            raise ValueError(f"{description} is missing identifier columns: " + ", ".join(missing))

    def _validate_dimensionless_row_count(self, frame: object, description: str) -> None:
        if self.identifiers:
            logger.debug(
                "Skipping dataset dimensionless row count for %s (data has dimensions)", description
            )
            return
        logger.debug("Check dataset dimensionless row count is at most one for %s", description)
        if self.backend.row_count(frame) > 1:
            raise ValueError(
                f"{description} contains duplicate identifiers "
                "(dimensionless profile frames allow at most one row)"
            )

    def _validate_unique_identifiers(self, frame: object, description: str) -> None:
        if not self.identifiers:
            logger.debug(
                "Skipping dataset identifier uniqueness for %s (no dimensions)", description
            )
            return
        logger.debug(
            "Check dataset identifier uniqueness for columns %s for %s",
            self.identifiers,
            description,
        )
        keys = self.backend.select(frame, self.identifiers)
        if self.backend.is_duplicated(keys):
            raise ValueError(f"{description} contains duplicate identifiers")

    def _validate_declared_types(
        self, frame: object, column_types: abc.Mapping[str, str] | None, description: str
    ) -> None:
        columns = set(self.backend.column_names(frame))
        types = {
            name: expected for name, expected in (column_types or {}).items() if name in columns
        }
        logger.debug(
            "Check dataset declared types of present columns %s for %s", types, description
        )
        self.backend.validate_types(frame, types)

    def merge(
        self,
        fragment: fragment_module.Fragment,
        *,
        fragment_id: str | None = None,
        join_cardinality: str = "m:m",
        broadcast_cardinality: str = "m:m",
    ) -> fragment_module.Fragment:
        """Merge a prepared contribution, optionally retaining it under an explicit ID.

        Delegate assembly and validation to Merge, then publish the checked frame.
        Complete-grain fragments use a full join; lower-resolution fragments
        broadcast over the existing scope. State changes only after assembly succeeds.

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
        merged = merge_module.Merge(self, fragment).execute(
            join_cardinality=join_cardinality,
            broadcast_cardinality=broadcast_cardinality,
        )
        self.dataframe = merged
        self.relations = tuple(
            dict.fromkeys(
                [
                    *self.relations,
                    *(column for column in fragment.keys if column not in self.identifiers),
                ]
            )
        )
        if fragment_id is not None:
            self.fragments[fragment_id] = fragment
        return fragment
