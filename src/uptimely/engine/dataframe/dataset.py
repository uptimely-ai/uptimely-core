"""Physical dataframe accumulation using explicit identifier columns."""

from collections import abc

from uptimely.library.merge import polars as merge_module

from . import backend as backend_module
from . import fragment as fragment_module


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
