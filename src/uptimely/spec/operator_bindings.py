"""Binding contracts for operator declarations."""

from __future__ import annotations

import dataclasses
import types
import typing

type PrimaryBindingKind = typing.Literal["seed", "read", "stage", "compute", "write", "workflow"]
type BindingKind = typing.Literal["seed", "read", "stage", "compute", "write", "workflow", "merge"]
type DataframeSource = typing.Literal[
    "none", "foreign_or_none", "foreign", "current", "dataset", "dataset_and_fragment"
]
type DataframeResult = typing.Literal["dataset", "fragment", "none"]
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


SEED: typing.Final[PrimaryBindingKind] = "seed"
READ: typing.Final[typing.Literal["read"]] = "read"
STAGE: typing.Final[PrimaryBindingKind] = "stage"
COMPUTE: typing.Final[PrimaryBindingKind] = "compute"
WRITE: typing.Final[typing.Literal["write"]] = "write"
WORKFLOW: typing.Final[PrimaryBindingKind] = "workflow"
MERGE: typing.Final[typing.Literal["merge"]] = "merge"

OPERATOR_BINDINGS: typing.Final[typing.Mapping[BindingKind, BindingContract]] = (
    types.MappingProxyType(
        {
            SEED: BindingContract(
                "Initialize the profile dataset.",
                True,
                (0, 1),
                "foreign_or_none",
                "dataset",
                "forbidden",
            ),
            READ: BindingContract(
                "Read a fragment from an external source.",
                True,
                (0,),
                "none",
                "fragment",
                "required",
            ),
            STAGE: BindingContract(
                "Prepare a fragment from another profile's dataset.",
                True,
                (1,),
                "foreign",
                "fragment",
                "required",
            ),
            COMPUTE: BindingContract(
                "Calculate features from the current dataset.",
                True,
                (1,),
                "current",
                "dataset",
                "forbidden",
            ),
            WRITE: BindingContract(
                "Write a dataset without producing a dataframe.",
                True,
                (1,),
                "dataset",
                "none",
                "forbidden",
            ),
            WORKFLOW: BindingContract(
                "Run an external workflow without dataframe inputs or outputs.",
                True,
                (0,),
                "none",
                "none",
                "forbidden",
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
    "READ",
    "SEED",
    "STAGE",
    "WORKFLOW",
    "WRITE",
    "DataframeResult",
    "DataframeSource",
    "MergeRequirement",
]
