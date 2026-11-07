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
    target: DataFrame | None,
    fragment: DataFrame,
    target_keys: collections.abc.Sequence[str],
    fragment_keys: collections.abc.Sequence[str] | None = None,
    *,
    join_cardinality: str = "m:m",
    broadcast_cardinality: str = "m:m",
) -> DataFrame:
    """Assemble a fragment into a target according to the keys each carries.

    Equal key sets use a full join, preserving either observation scope. A
    strict subset uses a left join, broadcasting over the target's scope; an
    empty subset uses a cross join. With no target, only a fragment carrying
    the complete target key set can initialize the result.

    Args:
        target: Accumulated target dataframe, or ``None`` for initialization.
        fragment: Contribution dataframe.
        target_keys: Complete key set defining the target grain.
        fragment_keys: Keys carried by the contribution. If omitted, infer the
            carried target keys from the fragment schema at runtime.
        join_cardinality: Cardinality constraint for full joins.
        broadcast_cardinality: Cardinality constraint for subset-key left joins.

    Returns:
        The assembled dataframe.

    Raises:
        ValueError: Fragment keys are incompatible or broadcasting has no target.
    """
    if fragment_keys is None:
        fragment_columns = set(_column_names(fragment))
        fragment_keys = [key for key in target_keys if key in fragment_columns]
    if not set(fragment_keys).issubset(target_keys):
        raise ValueError(
            "Fragment identifier columns must be a subset of accumulated dataset identifier columns"
        )

    same_grain = set(fragment_keys) == set(target_keys)
    if target is None:
        if not same_grain:
            raise ValueError(
                "A fragment with fewer identifier columns requires the accumulated main dataframe"
            )
        logger.debug("    - initialize from fragment (no join)")
        return fragment

    if type(target) is not type(fragment):
        target, fragment = target.lazy(), fragment.lazy()

    if same_grain:
        logger.debug("    - full join on %s (cardinality %s)", tuple(target_keys), join_cardinality)
        return full_join(target, fragment, target_keys, validate=join_cardinality)
    if not fragment_keys:
        logger.debug("    - cross join (dimensionless broadcast)")
        return cross_join(target, fragment)

    logger.debug(
        "    - left join on %s (cardinality %s)",
        tuple(fragment_keys),
        broadcast_cardinality,
    )
    return left_join(
        target,
        fragment,
        fragment_keys,
        validate=broadcast_cardinality,
    )


def _column_names(frame: DataFrame) -> list[str]:
    """Read column names without collecting a lazy dataframe."""
    if isinstance(frame, pl.LazyFrame):
        return frame.collect_schema().names()
    return frame.columns
