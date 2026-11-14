"""Custom merge functions for the example workflow."""

import polars as pl

from uptimely import function


@function(category="merge")
def merge_pump_inputs(
    dataset: pl.DataFrame | pl.LazyFrame | None,
    fragment: pl.DataFrame | pl.LazyFrame,
    dataset_identifiers: list[str],
) -> pl.DataFrame | pl.LazyFrame:
    """Full-join external inputs into the cooling-pump profile's current dataset."""
    if dataset is None:
        return fragment
    if isinstance(dataset, pl.DataFrame) and isinstance(fragment, pl.LazyFrame):
        dataset = dataset.lazy()
    elif isinstance(dataset, pl.LazyFrame) and isinstance(fragment, pl.DataFrame):
        fragment = fragment.lazy()
    return dataset.join(
        fragment,
        on=dataset_identifiers,
        how="full",
        coalesce=True,
        nulls_equal=True,
    )
