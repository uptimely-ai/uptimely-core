"""Function kind definitions and their spec-level execution rules."""

from __future__ import annotations

import dataclasses
import types
import typing

from . import arg_types

FunctionKindId = typing.Literal[
    "write", "read", "escape", "conform", "expand", "collapse", "vectorize"
]
ReturnKind = typing.Literal["dataframe", "none", "any"]
DataFrameInputScope = typing.Literal["none", "target", "foreign", "unrestricted"]
FeatureInputScope = typing.Literal["none", "target", "dataframe", "unrestricted"]
DimensionChange = typing.Literal["preserve", "add", "remove", "unrestricted"]
FragmentDimensions = typing.Literal["target", "subset", "not_applicable"]
RowCountRelation = typing.Literal["same", "unrestricted"]
KeyRelation = typing.Literal["identical", "unrestricted"]


@dataclasses.dataclass(frozen=True)
class FunctionKind:
    """Definition of one kind's validation contract and execution role.

    ``produces_features`` marks logical feature outputs; escape outputs are
    declared dependencies and are not materialized by the engine.
    ``dataframe_input_scope`` relates bound dataframes to the action's target;
    ``feature_input_scope`` describes where declared feature inputs may come from.
    ``dimension_change`` compares source and target dimension identities;
    ``fragment_dimensions`` constrains raw results; row-count and key relations
    compare a result with its accumulated target when specified.
    """

    id: FunctionKindId
    dataframe_inputs: int | None
    returns: ReturnKind
    produces_features: bool
    requires_feature_outputs: bool
    is_source: bool
    is_transformer: bool
    is_sink: bool
    is_effect: bool
    dimension_change: DimensionChange
    fragment_dimensions: FragmentDimensions
    row_count_relation: RowCountRelation
    key_relation: KeyRelation
    dataframe_input_scope: DataFrameInputScope = "unrestricted"
    feature_input_scope: FeatureInputScope = "unrestricted"


WRITE: typing.Final[FunctionKindId] = "write"
READ: typing.Final[FunctionKindId] = "read"
ESCAPE: typing.Final[FunctionKindId] = "escape"
CONFORM: typing.Final[FunctionKindId] = "conform"
EXPAND: typing.Final[FunctionKindId] = "expand"
COLLAPSE: typing.Final[FunctionKindId] = "collapse"
VECTORIZE: typing.Final[FunctionKindId] = "vectorize"

FUNCTION_KINDS: typing.Final[typing.Mapping[FunctionKindId, FunctionKind]] = types.MappingProxyType(
    {
        WRITE: FunctionKind(
            id=WRITE,
            dataframe_inputs=1,
            returns="none",
            produces_features=False,
            requires_feature_outputs=False,
            is_source=False,
            is_transformer=False,
            is_sink=True,
            is_effect=False,
            dataframe_input_scope="target",
            feature_input_scope="target",
            dimension_change="unrestricted",
            fragment_dimensions="not_applicable",
            row_count_relation="unrestricted",
            key_relation="unrestricted",
        ),
        READ: FunctionKind(
            id=READ,
            dataframe_inputs=0,
            returns=arg_types.DATAFRAME,
            produces_features=True,
            requires_feature_outputs=True,
            is_source=True,
            is_transformer=False,
            is_sink=False,
            is_effect=False,
            dataframe_input_scope="none",
            feature_input_scope="none",
            dimension_change="unrestricted",
            fragment_dimensions="target",
            row_count_relation="unrestricted",
            key_relation="unrestricted",
        ),
        ESCAPE: FunctionKind(
            id=ESCAPE,
            dataframe_inputs=None,
            returns="any",
            produces_features=True,
            requires_feature_outputs=False,
            is_source=False,
            is_transformer=False,
            is_sink=False,
            is_effect=True,
            dataframe_input_scope="unrestricted",
            feature_input_scope="unrestricted",
            dimension_change="unrestricted",
            fragment_dimensions="not_applicable",
            row_count_relation="unrestricted",
            key_relation="unrestricted",
        ),
        CONFORM: FunctionKind(
            id=CONFORM,
            dataframe_inputs=1,
            returns=arg_types.DATAFRAME,
            produces_features=True,
            requires_feature_outputs=True,
            is_source=True,
            is_transformer=False,
            is_sink=False,
            is_effect=False,
            dataframe_input_scope="foreign",
            feature_input_scope="dataframe",
            dimension_change="preserve",
            fragment_dimensions="target",
            row_count_relation="unrestricted",
            key_relation="unrestricted",
        ),
        EXPAND: FunctionKind(
            id=EXPAND,
            dataframe_inputs=1,
            returns=arg_types.DATAFRAME,
            produces_features=True,
            requires_feature_outputs=True,
            is_source=True,
            is_transformer=False,
            is_sink=False,
            is_effect=False,
            dataframe_input_scope="foreign",
            feature_input_scope="dataframe",
            dimension_change="add",
            fragment_dimensions="subset",
            row_count_relation="unrestricted",
            key_relation="unrestricted",
        ),
        COLLAPSE: FunctionKind(
            id=COLLAPSE,
            dataframe_inputs=1,
            returns=arg_types.DATAFRAME,
            produces_features=True,
            requires_feature_outputs=True,
            is_source=True,
            is_transformer=False,
            is_sink=False,
            is_effect=False,
            dataframe_input_scope="foreign",
            feature_input_scope="dataframe",
            dimension_change="remove",
            fragment_dimensions="target",
            row_count_relation="unrestricted",
            key_relation="unrestricted",
        ),
        VECTORIZE: FunctionKind(
            id=VECTORIZE,
            dataframe_inputs=1,
            returns=arg_types.DATAFRAME,
            produces_features=True,
            requires_feature_outputs=True,
            is_source=False,
            is_transformer=True,
            is_sink=False,
            is_effect=False,
            dataframe_input_scope="target",
            feature_input_scope="target",
            dimension_change="preserve",
            fragment_dimensions="target",
            row_count_relation="same",
            key_relation="identical",
        ),
    }
)


def kind_hint(returns: ReturnKind, dataframe_inputs: int) -> str:
    """Suggest explicitly declared kinds matching a function contract."""
    matches = [
        kind
        for kind, definition in FUNCTION_KINDS.items()
        if kind != ESCAPE
        and definition.returns == returns
        and definition.dataframe_inputs == dataframe_inputs
    ]
    if matches:
        suggestions = ", ".join(matches)
        return (
            f" This function's declared return kind and {dataframe_inputs} dataframe "
            f"argument(s) fit kind(s): {suggestions}. Declare the intended "
            "kind explicitly."
        )
    return (
        f" No controlled kind matches this function's declared return kind and "
        f"{dataframe_inputs} dataframe argument(s). If it performs intentional "
        "uncontrolled work, declare kind=escape explicitly."
    )


__all__ = [
    "COLLAPSE",
    "CONFORM",
    "DataFrameInputScope",
    "DimensionChange",
    "ESCAPE",
    "EXPAND",
    "FeatureInputScope",
    "FragmentDimensions",
    "FUNCTION_KINDS",
    "FunctionKind",
    "FunctionKindId",
    "KeyRelation",
    "READ",
    "RowCountRelation",
    "ReturnKind",
    "VECTORIZE",
    "WRITE",
    "kind_hint",
]
