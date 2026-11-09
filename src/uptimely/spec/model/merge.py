"""Default merge declarations used by Spec operators."""

from __future__ import annotations

import typing

from . import binding, functions

if typing.TYPE_CHECKING:
    from .spec import Spec

DEFAULT_FUNCTION = functions.FunctionTemplate(
    id="merge_by_grain",
    name="Merge By Grain",
    description="Merge a fragment into the target by grain keys.",
    returns="dataframe",
    entrypoint="uptimely.library.merge.polars:merge_by_grain",
    args={
        "target": functions.Argument(id="target", type="dataframe | null"),
        "fragment": functions.Argument(id="fragment", type="dataframe"),
        "target_keys": functions.Argument(id="target_keys", type="array[string]"),
    },
)
DEFAULT_BINDING = binding.Binding(
    function=DEFAULT_FUNCTION.id,
    args={
        "target": "$profiles.@.dataset",
        "fragment": "$operators.@.fragment",
        "target_keys": "$profiles.@.grain.ids",
    },
)


def collect_default_merge(spec: Spec) -> None:
    """Include the builtin declaration only when a binding explicitly selects it."""
    for profile in spec.profiles.values():
        for operator in profile.assembly.values():
            if (
                operator.merge is not None
                and operator.merge.function == DEFAULT_FUNCTION.id
                and spec.functions.get(DEFAULT_FUNCTION.id) is None
            ):
                spec.functions.root[DEFAULT_FUNCTION.id] = DEFAULT_FUNCTION.model_copy(deep=True)
