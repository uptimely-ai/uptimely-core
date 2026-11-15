"""Explicit selection of the builtin grain merge."""

from . import assembly, ref


def default() -> assembly.Bind:
    """Return a binding that merges a fragment into its dataset by grain keys."""
    return assembly.Bind(
        ref.function(
            "uptimely.library.merge.polars:merge_by_grain",
            returns="dataframe",
            args={
                "dataset": "dataframe | null",
                "fragment": "dataframe",
                "dataset_identifiers": "array[string]",
            },
            description="Merge a fragment into the dataset by grain keys.",
        ),
        dataset=ref.dataset(),
        fragment=ref.fragment(),
        dataset_identifiers=ref.profile().grain.ids,
    )


default_merge = default
