"""Binding contracts for operator declarations."""

from __future__ import annotations

import dataclasses
import types
import typing

type PrimaryBindingKind = typing.Literal["compute"]
type BindingKind = typing.Literal["compute", "merge"]
type DataframeSource = typing.Literal[
    "none", "foreign_or_none", "foreign", "current", "dataset", "dataset_and_fragment"
]
type DataframeResult = typing.Literal["dataset", "fragment", "none", "dataset_or_fragment_or_none"]
type MergeRequirement = typing.Literal["required", "forbidden", "additional"]


@dataclasses.dataclass(frozen=True)
class BindingContract:
    """Describe a binding's dataframe contract independently of logical features.

    Args:
        description: Purpose of the binding.
        primary: Whether this binding determines the operator's primary binding role.
        dataframe_inputs: Allowed numbers of dataframe inputs.
        dataframe_source: Origin of the dataframe inputs.
        dataframe_result: How the dataframe result is used.
        merge: Whether a separate merge is required, forbidden, or additional.
    """

    description: str
    primary: bool
    dataframe_inputs: tuple[int, ...]
    dataframe_source: DataframeSource
    dataframe_result: DataframeResult
    merge: MergeRequirement


COMPUTE: typing.Final[PrimaryBindingKind] = "compute"
MERGE: typing.Final[typing.Literal["merge"]] = "merge"

OPERATOR_BINDINGS: typing.Final[typing.Mapping[BindingKind, BindingContract]] = (
    types.MappingProxyType(
        {
            COMPUTE: BindingContract(
                "Run the primary function with zero or one dataframe input.",
                True,
                (0, 1),
                "dataset",
                "dataset_or_fragment_or_none",
                "additional",
            ),
            MERGE: BindingContract(
                "Combine a fragment with the current dataset.",
                False,
                (2,),
                "dataset_and_fragment",
                "dataset",
                "additional",
            ),
        }
    )
)

__all__ = [
    "BindingContract",
    "BindingKind",
    "COMPUTE",
    "MERGE",
    "OPERATOR_BINDINGS",
    "PrimaryBindingKind",
    "DataframeResult",
    "DataframeSource",
    "MergeRequirement",
]
