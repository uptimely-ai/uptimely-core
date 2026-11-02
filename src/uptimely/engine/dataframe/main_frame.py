"""Physical dataframe accumulation using explicit identifier columns."""

import logging
from collections import abc

from . import backend as backend_module
from . import fragment as fragment_module

logger = logging.getLogger(__name__)


class MainFrame:
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
        if not set(fragment.dimensions).issubset(self.id_columns):
            raise ValueError(
                "Fragment identifier columns must be a subset of main frame identifier columns"
            )
        same_grain = set(fragment.dimensions) == set(self.id_columns)
        if self.dataframe is None:
            if not same_grain:
                raise ValueError(
                    "A fragment with fewer identifier columns requires the accumulated "
                    "main dataframe"
                )
            logger.debug("    - initialize from fragment (no join)")
            merged = fragment.dataframe
        else:
            left, right = self.dataframe, fragment.dataframe
            if type(left) is not type(right):
                left, right = self.backend.lazy(left), self.backend.lazy(right)
            if same_grain:
                logger.debug(
                    "    - full join on %s (cardinality %s)", self.id_columns, join_cardinality
                )
                merged = self.backend.join(
                    left,
                    right,
                    self.id_columns,
                    validate=join_cardinality,
                )
            elif not fragment.dimensions:
                logger.debug("    - cross join (dimensionless broadcast)")
                merged = self.backend.cross_join(left, right)
            else:
                logger.debug(
                    "    - left join on %s (cardinality %s)",
                    fragment.dimensions,
                    broadcast_cardinality,
                )
                merged = self.backend.left_join(
                    left,
                    right,
                    fragment.dimensions,
                    validate=broadcast_cardinality,
                )
        self.dataframe = merged
        if fragment_id is not None:
            self.fragments[fragment_id] = fragment
        return fragment
