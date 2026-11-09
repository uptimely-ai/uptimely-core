"""Explicit selection of the builtin grain merge."""

from . import assembly, ref


def default_merge() -> assembly.Binding:
    """Return a binding that merges a fragment into its dataset by grain keys."""
    return assembly.Binding(
        function=ref.function(
            "uptimely.library.merge.polars:merge_by_grain",
            returns="dataframe",
            args={
                "dataset": "dataframe | null",
                "fragment": "dataframe",
                "dataset_keys": "array[string]",
            },
            description="Merge a fragment into the dataset by grain keys.",
        ),
        arguments={
            "dataset": ref.dataset(),
            "fragment": ref.fragment(),
            "dataset_keys": ref.profile().grain.ids,
        },
    )
