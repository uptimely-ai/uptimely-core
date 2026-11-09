"""Explicit selection of the builtin grain merge."""

from . import assembly, ref


def default_merge() -> assembly.Binding:
    """Return a binding that merges a fragment into its target by grain keys."""
    return assembly.Binding(
        function=ref.function(
            "uptimely.library.merge.polars:merge_by_grain",
            returns="dataframe",
            args={
                "target": "dataframe | null",
                "fragment": "dataframe",
                "target_keys": "array[string]",
            },
            description="Merge a fragment into the target by grain keys.",
        ),
        arguments={
            "target": ref.dataset(),
            "fragment": ref.fragment(),
            "target_keys": ref.profile().grain.ids,
        },
    )
