"""Derived operator labels and their spec-level execution rules."""

from __future__ import annotations

import dataclasses
import types
import typing

from . import arg_types

__all__ = [
    "CONFORM",
    "COLLAPSE",
    "DataFrameInputScope",
    "DataFrameInputViolation",
    "DimensionChange",
    "ESCAPE",
    "EXPAND",
    "ExistingDataRelation",
    "FeatureInputScope",
    "FragmentDimensions",
    "OPERATOR_KINDS",
    "OperatorKind",
    "OperatorKindId",
    "KeyRelation",
    "MERGE",
    "READ",
    "ReturnKind",
    "RowCountRelation",
    "RowOrderRelation",
    "VECTORIZE",
    "WRITE",
    "arg_types",
]

OperatorKindId = typing.Literal[
    "write", "read", "escape", "conform", "expand", "collapse", "vectorize", "merge"
]
ReturnKind = typing.Literal["dataframe", "none", "any"]
DataFrameInputScope = typing.Literal["none", "target", "foreign", "unrestricted"]
FeatureInputScope = typing.Literal["none", "target", "dataframe", "unrestricted"]
DimensionChange = typing.Literal["preserve", "add", "remove", "unrestricted"]
FragmentDimensions = typing.Literal["target", "subset", "not_applicable"]
RowCountRelation = typing.Literal["same", "unrestricted"]
KeyRelation = typing.Literal["identical", "unrestricted"]
RowOrderRelation = typing.Literal["preserve", "unrestricted"]
ExistingDataRelation = typing.Literal["preserve", "unrestricted"]
DataFrameInputViolation = typing.Literal[
    "missing_target",
    "foreign_target_input",
    "target_as_foreign_input",
    "missing_source",
]


@dataclasses.dataclass(frozen=True)
class OperatorKind:
    """Definition of one kind's validation contract and execution role.

    ``produces_features`` marks logical feature outputs; escape outputs are
    declared dependencies and are not materialized by the engine.
    ``dataframe_input_scope`` relates bound dataframes to the operator's target;
    ``feature_input_scope`` describes where declared feature inputs may come from.
    ``dimension_change`` compares source and target dimension identities;
    ``fragment_dimensions`` constrains raw results; row-count, key, row-order,
    and existing-data relations compare a result with its accumulated target.
    """

    id: OperatorKindId
    dataframe_inputs: int | None
    returns: ReturnKind
    produces_features: bool
    requires_feature_outputs: bool
    is_source: bool
    is_transformer: bool
    produces_fragment: bool
    is_sink: bool
    is_effect: bool
    dimension_change: DimensionChange
    fragment_dimensions: FragmentDimensions
    row_count_relation: RowCountRelation
    key_relation: KeyRelation
    row_order_relation: RowOrderRelation
    existing_data_relation: ExistingDataRelation
    dataframe_input_scope: DataFrameInputScope = "unrestricted"
    feature_input_scope: FeatureInputScope = "unrestricted"

    def dataframe_input_violations(
        self,
        target_profile_id: str,
        argument_profile_ids: tuple[str | None, ...],
        resolved_profile_ids: frozenset[str],
        inferred_profile_id: str | None,
    ) -> tuple[DataFrameInputViolation, ...]:
        """Return dataframe-input contract violations for one operator."""
        violations: list[DataFrameInputViolation] = []
        if self.dataframe_input_scope == "target":
            if target_profile_id not in resolved_profile_ids:
                violations.append("missing_target")
            if resolved_profile_ids - {target_profile_id}:
                violations.append("foreign_target_input")
        if (
            self.dataframe_input_scope == "foreign"
            and self.dataframe_inputs is not None
            and len(argument_profile_ids) == self.dataframe_inputs
            and argument_profile_ids
            and argument_profile_ids[0] == target_profile_id
        ):
            violations.append("target_as_foreign_input")
        if (
            self.dimension_change == "remove"
            and inferred_profile_id is not None
            and inferred_profile_id not in resolved_profile_ids
        ):
            violations.append("missing_source")
        return tuple(violations)


WRITE: typing.Final[OperatorKindId] = "write"
READ: typing.Final[OperatorKindId] = "read"
ESCAPE: typing.Final[OperatorKindId] = "escape"
CONFORM: typing.Final[OperatorKindId] = "conform"
EXPAND: typing.Final[OperatorKindId] = "expand"
COLLAPSE: typing.Final[OperatorKindId] = "collapse"
VECTORIZE: typing.Final[OperatorKindId] = "vectorize"
MERGE: typing.Final[OperatorKindId] = "merge"

OPERATOR_KINDS: typing.Final[typing.Mapping[OperatorKindId, OperatorKind]] = types.MappingProxyType(
    {
        WRITE: OperatorKind(
            id=WRITE,
            dataframe_inputs=None,
            returns="none",
            produces_features=False,
            requires_feature_outputs=False,
            is_source=False,
            is_transformer=False,
            produces_fragment=False,
            is_sink=True,
            is_effect=False,
            dataframe_input_scope="unrestricted",
            feature_input_scope="unrestricted",
            dimension_change="unrestricted",
            fragment_dimensions="not_applicable",
            row_count_relation="unrestricted",
            key_relation="unrestricted",
            row_order_relation="unrestricted",
            existing_data_relation="unrestricted",
        ),
        READ: OperatorKind(
            id=READ,
            dataframe_inputs=0,
            returns=arg_types.DATAFRAME,
            produces_features=True,
            requires_feature_outputs=True,
            is_source=True,
            is_transformer=False,
            produces_fragment=True,
            is_sink=False,
            is_effect=False,
            dataframe_input_scope="none",
            feature_input_scope="none",
            dimension_change="unrestricted",
            fragment_dimensions="target",
            row_count_relation="unrestricted",
            key_relation="unrestricted",
            row_order_relation="unrestricted",
            existing_data_relation="unrestricted",
        ),
        ESCAPE: OperatorKind(
            id=ESCAPE,
            dataframe_inputs=None,
            returns="any",
            produces_features=True,
            requires_feature_outputs=False,
            is_source=False,
            is_transformer=False,
            produces_fragment=False,
            is_sink=False,
            is_effect=True,
            dataframe_input_scope="unrestricted",
            feature_input_scope="unrestricted",
            dimension_change="unrestricted",
            fragment_dimensions="not_applicable",
            row_count_relation="unrestricted",
            key_relation="unrestricted",
            row_order_relation="unrestricted",
            existing_data_relation="unrestricted",
        ),
        CONFORM: OperatorKind(
            id=CONFORM,
            dataframe_inputs=1,
            returns=arg_types.DATAFRAME,
            produces_features=True,
            requires_feature_outputs=True,
            is_source=True,
            is_transformer=False,
            produces_fragment=True,
            is_sink=False,
            is_effect=False,
            dataframe_input_scope="foreign",
            feature_input_scope="dataframe",
            dimension_change="preserve",
            fragment_dimensions="target",
            row_count_relation="unrestricted",
            key_relation="unrestricted",
            row_order_relation="unrestricted",
            existing_data_relation="unrestricted",
        ),
        EXPAND: OperatorKind(
            id=EXPAND,
            dataframe_inputs=1,
            returns=arg_types.DATAFRAME,
            produces_features=True,
            requires_feature_outputs=True,
            is_source=True,
            is_transformer=False,
            produces_fragment=True,
            is_sink=False,
            is_effect=False,
            dataframe_input_scope="foreign",
            feature_input_scope="dataframe",
            dimension_change="add",
            fragment_dimensions="subset",
            row_count_relation="unrestricted",
            key_relation="unrestricted",
            row_order_relation="unrestricted",
            existing_data_relation="unrestricted",
        ),
        COLLAPSE: OperatorKind(
            id=COLLAPSE,
            dataframe_inputs=1,
            returns=arg_types.DATAFRAME,
            produces_features=True,
            requires_feature_outputs=True,
            is_source=True,
            is_transformer=False,
            produces_fragment=True,
            is_sink=False,
            is_effect=False,
            dataframe_input_scope="foreign",
            feature_input_scope="dataframe",
            dimension_change="remove",
            fragment_dimensions="target",
            row_count_relation="unrestricted",
            key_relation="unrestricted",
            row_order_relation="unrestricted",
            existing_data_relation="unrestricted",
        ),
        VECTORIZE: OperatorKind(
            id=VECTORIZE,
            dataframe_inputs=1,
            returns=arg_types.DATAFRAME,
            produces_features=True,
            requires_feature_outputs=True,
            is_source=False,
            is_transformer=True,
            produces_fragment=False,
            is_sink=False,
            is_effect=False,
            dataframe_input_scope="target",
            feature_input_scope="target",
            dimension_change="preserve",
            fragment_dimensions="not_applicable",
            row_count_relation="same",
            key_relation="identical",
            row_order_relation="preserve",
            existing_data_relation="preserve",
        ),
        MERGE: OperatorKind(
            id=MERGE,
            dataframe_inputs=2,
            returns=arg_types.DATAFRAME,
            produces_features=False,
            requires_feature_outputs=False,
            is_source=False,
            is_transformer=False,
            produces_fragment=False,
            is_sink=False,
            is_effect=False,
            dataframe_input_scope="unrestricted",
            feature_input_scope="none",
            dimension_change="preserve",
            fragment_dimensions="not_applicable",
            row_count_relation="unrestricted",
            key_relation="unrestricted",
            row_order_relation="unrestricted",
            existing_data_relation="unrestricted",
        ),
    }
)


__all__ = [
    "COLLAPSE",
    "CONFORM",
    "DataFrameInputScope",
    "DimensionChange",
    "ESCAPE",
    "ExistingDataRelation",
    "EXPAND",
    "FeatureInputScope",
    "FragmentDimensions",
    "OPERATOR_KINDS",
    "OperatorKind",
    "OperatorKindId",
    "KeyRelation",
    "MERGE",
    "READ",
    "RowCountRelation",
    "RowOrderRelation",
    "ReturnKind",
    "VECTORIZE",
    "WRITE",
]
