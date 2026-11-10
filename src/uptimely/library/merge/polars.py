"""Polars dataframe merge functions."""

from __future__ import annotations

import collections.abc
import logging

import polars as pl

DataFrame = pl.DataFrame | pl.LazyFrame

logger = logging.getLogger(__name__)


def full_join(
    left: DataFrame,
    right: DataFrame,
    keys: collections.abc.Sequence[str],
    *,
    validate: str = "1:1",
) -> DataFrame:
    """Full-join two dataframes on keys, matching nulls and coalescing key columns.

    With no keys, join on a temporary constant key, preserving either side
    when the other dataframe is empty.

    Args:
        left: The left dataframe.
        right: The right dataframe.
        keys: Columns used to match rows.
        validate: Polars join cardinality constraint.

    Returns:
        The full-joined dataframe.
    """
    if not keys:
        key = "__join_key"
        columns = set(_column_names(left)) | set(_column_names(right))
        while key in columns:
            key += "_"
        return (
            left.with_columns(pl.lit(0).alias(key))
            .join(
                right.with_columns(pl.lit(0).alias(key)),
                on=key,
                how="full",
                coalesce=True,
                validate=validate,
            )
            .drop(key)
        )
    return left.join(
        right,
        on=list(keys),
        how="full",
        coalesce=True,
        validate=validate,
        nulls_equal=True,
    )


def left_join(
    left: DataFrame,
    right: DataFrame,
    keys: collections.abc.Sequence[str],
    *,
    validate: str = "m:1",
) -> DataFrame:
    """Left-join two dataframes on keys, matching nulls and coalescing key columns.

    Args:
        left: The left dataframe.
        right: The right dataframe.
        keys: Columns used to match rows.
        validate: Polars join cardinality constraint.

    Returns:
        The left-joined dataframe.
    """
    return left.join(
        right,
        on=list(keys),
        how="left",
        coalesce=True,
        validate=validate,
        nulls_equal=True,
    )


def cross_join(left: DataFrame, right: DataFrame) -> DataFrame:
    """Return the Cartesian product of two dataframes.

    Args:
        left: The left dataframe.
        right: The right dataframe.

    Returns:
        The Cartesian product.
    """
    return left.join(right, how="cross")


def merge_by_grain(
    dataset: DataFrame | None,
    fragment: DataFrame,
    dataset_identifiers: collections.abc.Sequence[str],
    fragment_keys: collections.abc.Sequence[str] | None = None,
    *,
    key_columns: collections.abc.Sequence[str] = (),
    join_cardinality: str = "m:m",
    broadcast_cardinality: str = "m:m",
) -> DataFrame:
    """Assemble a fragment into a dataset according to the keys each carries.

    Fragments carrying the complete grain use a full join, preserving either
    observation scope. Carried relations use a left join,
    broadcasting over the dataset's scope; no keys uses a cross join.
    With no dataset, only a fragment carrying the complete dataset key set
    can initialize the result.

    Args:
        dataset: Accumulated dataset dataframe, or ``None`` for initialization.
        fragment: Contribution dataframe.
        dataset_identifiers: Columns identifying dataset rows at its grain.
        fragment_keys: Keys carried by the contribution. If omitted, infer the
            matching grain and relation columns from the fragment schema at runtime.
        key_columns: Grain keys and declared relation columns.
            Present columns are retained and used to join lower-resolution fragments.
        join_cardinality: Cardinality constraint for full joins.
        broadcast_cardinality: Cardinality constraint for subset-key left joins.

    Returns:
        The assembled dataframe.

    Raises:
        ValueError: Fragment keys are incompatible or broadcasting has no dataset.
    """
    allowed_keys = list(dict.fromkeys([*dataset_identifiers, *key_columns]))
    if fragment_keys is None:
        fragment_columns = set(_column_names(fragment))
        fragment_keys = [key for key in allowed_keys if key in fragment_columns]
    if not set(fragment_keys).issubset(allowed_keys):
        raise ValueError(
            "Fragment identifier columns must be a subset of accumulated dataset identifier columns"
        )

    same_grain = set(dataset_identifiers).issubset(fragment_keys)
    if dataset is None:
        if not same_grain:
            raise ValueError(
                "A fragment with fewer identifier columns requires the accumulated dataset"
            )
        logger.debug("Initialize from fragment (no join)")
        return fragment

    if type(dataset) is not type(fragment):
        dataset, fragment = dataset.lazy(), fragment.lazy()

    if same_grain:
        logger.debug(
            "Full join on %s (cardinality %s)", tuple(dataset_identifiers), join_cardinality
        )
        shared_relations = [
            key
            for key in key_columns
            if key not in dataset_identifiers
            and key in _column_names(dataset)
            and key in _column_names(fragment)
        ]
        if shared_relations:
            columns = set(_column_names(dataset)) | set(_column_names(fragment))
            suffix = "__identifier"
            while any(key + suffix in columns for key in shared_relations):
                suffix += "_"
            renamed = {key: key + suffix for key in shared_relations}
            result = full_join(
                dataset, fragment.rename(renamed), dataset_identifiers, validate=join_cardinality
            )
            return result.with_columns(
                pl.coalesce(key, renamed[key]).alias(key) for key in shared_relations
            ).drop(list(renamed.values()))
        return full_join(dataset, fragment, dataset_identifiers, validate=join_cardinality)
    missing_keys = set(fragment_keys) - set(_column_names(dataset))
    if missing_keys:
        raise ValueError(
            "Matching keys are missing from the dataset: " + ", ".join(sorted(missing_keys))
        )
    if not fragment_keys:
        logger.debug("Cross join (dimensionless broadcast)")
        return cross_join(dataset, fragment)

    logger.debug(
        "Left join on %s (cardinality %s)",
        tuple(fragment_keys),
        broadcast_cardinality,
    )
    return left_join(
        dataset,
        fragment,
        fragment_keys,
        validate=broadcast_cardinality,
    )


def _column_names(frame: DataFrame) -> list[str]:
    """Read column names without collecting a lazy dataframe."""
    if isinstance(frame, pl.LazyFrame):
        return frame.collect_schema().names()
    return frame.columns
