"""Default merge declarations used by Spec operators."""

from __future__ import annotations

import typing

from uptimely.spec import functions as function_kinds

from . import binding, functions

if typing.TYPE_CHECKING:
    from .spec import Spec

DEFAULT_FUNCTION = functions.FunctionTemplate(
    id="__uptimely_merge_by_grain",
    name="Automatic merge by grain",
    kind="merge",
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
        "target": "$profiles.@.dataframe",
        "fragment": "$operators.@.fragment",
        "target_keys": "$profiles.@.grain.ids",
    },
)


def bind_default_merges(spec: Spec) -> None:
    """Attach the default merge binding and function to fragment-producing operators."""
    added_default = False
    for profile in spec.profiles.values():
        for operator in profile.assembly.values():
            function = spec.functions.get(operator.compute.function)
            if (
                operator.merge is None
                and function is not None
                and function_kinds.FUNCTION_KINDS[function.kind].produces_fragment
            ):
                operator.bind_default_merge()
                added_default = True
    if added_default and spec.functions.get(DEFAULT_FUNCTION.id) is None:
        spec.functions.root[DEFAULT_FUNCTION.id] = DEFAULT_FUNCTION.model_copy(deep=True)
