"""Profile models for spec documents."""

from __future__ import annotations

import dataclasses
import functools
import typing

import pydantic

from uptimely.spec import arg_types, operator_bindings, selectors
from uptimely.spec import row_context as uptimely_row_context

from . import base, binding, binding_argument
from . import dimension as dimension_module


class OperatorBindingRole:
    """Roles of bindings declared by an operator."""

    Value = typing.Literal["compute", "merge"]
    COMPUTE: typing.Final = operator_bindings.COMPUTE
    MERGE: typing.Final = operator_bindings.MERGE


class OperatorExecutionForm:
    """Binding combinations available to an operator."""

    Value = typing.Literal["compute", "compute + merge"]
    COMPUTE: typing.Final = operator_bindings.COMPUTE
    COMPUTE_AND_MERGE: typing.Final = "compute + merge"


class OperatorSourceStatus:
    """Resolution status of an operator's input sources."""

    Value = typing.Literal["resolved", "missing", "ambiguous", "invalid_reference"]
    RESOLVED: typing.Final = "resolved"
    MISSING: typing.Final = "missing"
    AMBIGUOUS: typing.Final = "ambiguous"
    INVALID_REFERENCE: typing.Final = "invalid_reference"


class GrainRelationship:
    """Relationship between the grains of source and target profiles."""

    Value = typing.Literal[
        "same", "expand", "collapse", "emerge", "vanish", "unrelated", "not_applicable"
    ]
    SAME: typing.Final = "same"
    EXPAND: typing.Final = "expand"
    COLLAPSE: typing.Final = "collapse"
    EMERGE: typing.Final = "emerge"
    VANISH: typing.Final = "vanish"
    UNRELATED: typing.Final = "unrelated"
    NOT_APPLICABLE: typing.Final = "not_applicable"


class DataFrameInputScope:
    """Allowed origins of dataframe inputs."""

    Value = typing.Literal["none", "target", "foreign", "unrestricted"]
    NONE: typing.Final = "none"
    TARGET: typing.Final = "target"
    FOREIGN: typing.Final = "foreign"
    UNRESTRICTED: typing.Final = "unrestricted"


class FeatureInputScope:
    """Allowed origins of feature inputs."""

    Value = typing.Literal["none", "target", "dataframe", "unrestricted"]
    NONE: typing.Final = "none"
    TARGET: typing.Final = "target"
    DATAFRAME: typing.Final = "dataframe"
    UNRESTRICTED: typing.Final = "unrestricted"


class DimensionChange:
    """Allowed changes to dimensions."""

    Value = typing.Literal["preserve", "add", "remove", "unrestricted"]
    PRESERVE: typing.Final = "preserve"
    ADD: typing.Final = "add"
    REMOVE: typing.Final = "remove"
    UNRESTRICTED: typing.Final = "unrestricted"


class FragmentDimensions:
    """Relationship between fragment and target dimensions."""

    Value = typing.Literal["target", "subset", "not_applicable"]
    TARGET: typing.Final = "target"
    SUBSET: typing.Final = "subset"
    NOT_APPLICABLE: typing.Final = "not_applicable"


class RowCountRelation:
    """Relationship between input and output row counts."""

    Value = typing.Literal["same", "unrestricted"]
    SAME: typing.Final = "same"
    UNRESTRICTED: typing.Final = "unrestricted"


class KeyRelation:
    """Relationship between input and output keys."""

    Value = typing.Literal["identical", "unrestricted"]
    IDENTICAL: typing.Final = "identical"
    UNRESTRICTED: typing.Final = "unrestricted"


class RowOrderRelation:
    """Relationship between input and output row order."""

    Value = typing.Literal["preserve", "unrestricted"]
    PRESERVE: typing.Final = "preserve"
    UNRESTRICTED: typing.Final = "unrestricted"


class ExistingDataRelation:
    """Relationship between input and output data."""

    Value = typing.Literal["preserve", "unrestricted"]
    PRESERVE: typing.Final = "preserve"
    UNRESTRICTED: typing.Final = "unrestricted"


@dataclasses.dataclass(frozen=True)
class OperatorExecutionContract:
    """Validation and execution policies derived from an operator's declaration."""

    produces_features: bool
    is_source: bool
    is_transformer: bool
    is_sink: bool
    is_effect: bool
    dimension_change: DimensionChange.Value
    fragment_dimensions: FragmentDimensions.Value
    row_count_relation: RowCountRelation.Value
    key_relation: KeyRelation.Value
    row_order_relation: RowOrderRelation.Value
    existing_data_relation: ExistingDataRelation.Value
    dataframe_input_scope: DataFrameInputScope.Value
    feature_input_scope: FeatureInputScope.Value


if typing.TYPE_CHECKING:
    from .spec import OperatorKey, ProfileKey, Spec


class Feature(base.StrictModel):
    """A profile feature's logical metadata."""

    id: str = pydantic.Field(exclude=True)
    name: str | None = None
    description: str | None = None
    type: str | None = None
    unit: str | None = None

    @pydantic.model_validator(mode="after")
    def generate_name(self) -> typing.Self:
        """Generate a display name from the feature ID when one is not supplied."""
        if self.name is None:
            self.name = base.humanize_identifier(self.id)
        return self


class Interface(base.StrictModel):
    """Explicit data prerequisites and produced features for one operator."""

    inputs: list[str] = pydantic.Field(default_factory=list)
    outputs: list[str] = pydantic.Field(default_factory=list)

    @functools.cached_property
    def input_ids(self) -> list[str]:
        """Return normalized input feature IDs once."""
        return [value.removeprefix(selectors.FEATURE_PREFIX) for value in self.inputs]

    @functools.cached_property
    def output_ids(self) -> list[str]:
        """Return normalized output feature IDs once."""
        return [value.removeprefix(selectors.FEATURE_PREFIX) for value in self.outputs]

    @pydantic.field_validator("inputs", "outputs")
    @classmethod
    def validate_references(cls, values: list[str]) -> list[str]:
        """Require distinct feature references without value selectors."""
        if any(
            not value.startswith(selectors.FEATURE_PREFIX)
            or "." in value[len(selectors.FEATURE_PREFIX) :]
            or not value[len(selectors.FEATURE_PREFIX) :]
            or value[len(selectors.FEATURE_PREFIX) :] == selectors.CURRENT_ID
            for value in values
        ):
            raise ValueError("Operator interface must use $features.<id> references")
        if len(values) != len(set(values)):
            raise ValueError("Operator interface references must not repeat")
        return values


class Operator(base.StrictModel):
    """A computation with declared feature inputs, outputs, and optional merge."""

    id: str = pydantic.Field(exclude=True)
    interface: Interface = pydantic.Field(default_factory=Interface)
    row_context: uptimely_row_context.RowContext | None = None
    compute: binding.Binding
    is_workflow: bool = False
    merge: binding.Binding | None = None

    @property
    def bindings(self) -> dict[OperatorBindingRole.Value, binding.Binding]:
        """Return compute and optional merge bindings in declaration order."""
        bindings: dict[OperatorBindingRole.Value, binding.Binding] = {
            OperatorBindingRole.COMPUTE: self.compute
        }
        if self.merge is not None:
            bindings[OperatorBindingRole.MERGE] = self.merge
        return bindings

    @property
    def execution_form(self) -> OperatorExecutionForm.Value:
        """Return whether this operator has a compute binding alone or with merge."""
        return (
            OperatorExecutionForm.COMPUTE_AND_MERGE
            if self.merge is not None
            else OperatorExecutionForm.COMPUTE
        )

    @property
    def binding_roles(self) -> tuple[OperatorBindingRole.Value, ...]:
        """Return the execution roles declared by this operator."""
        return (
            (OperatorBindingRole.COMPUTE, OperatorBindingRole.MERGE)
            if self.merge is not None
            else (OperatorBindingRole.COMPUTE,)
        )

    @property
    def input_features(self) -> list[str]:
        """Return identifiers of declared feature dependencies."""
        return self.interface.input_ids

    @property
    def output_features(self) -> list[str]:
        """Return identifiers of declared logical feature outputs."""
        return self.interface.output_ids

    @property
    def arguments(self) -> dict[str, binding_argument.BindingArgument]:
        """Return this operator's bound argument objects."""
        return self.compute.args

    def resolve_args(
        self,
        function_id: str,
        profile_id: str,
        identifiers_by_profile: typing.Mapping[str, typing.Sequence[str]],
        resources: binding_argument.BindingResources,
        *,
        role: OperatorBindingRole.Value = OperatorBindingRole.COMPUTE,
        feature_id: str | None = None,
    ) -> dict[str, object]:
        """Resolve arguments from the binding selected by its execution role."""
        if role == OperatorBindingRole.COMPUTE:
            selected_binding = self.compute
        elif role == OperatorBindingRole.MERGE and self.merge is not None:
            selected_binding = self.merge
            feature_id = None
        else:
            raise ValueError(f"Operator {self.id} has no {role} binding")
        if selected_binding.function != function_id:
            raise ValueError(
                f"Operator {self.id} {role} binding selects {selected_binding.function}, "
                f"not {function_id}"
            )
        return selected_binding.resolve_args(
            profile_id,
            feature_id,
            identifiers_by_profile,
            resources,
            row_context=self.row_context,
        )

    def execution_contract(
        self,
        *,
        returns: str,
        target_profile: ProfileKey,
        dataframe_sources: typing.Sequence[ProfileKey],
        grain_relationships: typing.Mapping[ProfileKey, GrainRelationship.Value],
    ) -> OperatorExecutionContract:
        """Derive validation policies from this declaration and its dataframe sources."""
        if returns != arg_types.DATAFRAME:
            is_workflow = self.is_workflow
            return OperatorExecutionContract(
                produces_features=returns == "any" or is_workflow,
                is_source=False,
                is_transformer=False,
                is_sink=returns == "none" or is_workflow,
                is_effect=returns == "any" and not is_workflow,
                dimension_change=DimensionChange.UNRESTRICTED,
                fragment_dimensions=FragmentDimensions.NOT_APPLICABLE,
                row_count_relation=RowCountRelation.UNRESTRICTED,
                key_relation=KeyRelation.UNRESTRICTED,
                row_order_relation=RowOrderRelation.UNRESTRICTED,
                existing_data_relation=ExistingDataRelation.UNRESTRICTED,
                dataframe_input_scope=DataFrameInputScope.UNRESTRICTED,
                feature_input_scope=FeatureInputScope.UNRESTRICTED,
            )

        has_target_source = target_profile in dataframe_sources
        has_foreign_source = any(source != target_profile for source in dataframe_sources)
        if has_target_source:
            return OperatorExecutionContract(
                produces_features=True,
                is_source=False,
                is_transformer=True,
                is_sink=False,
                is_effect=False,
                dimension_change=DimensionChange.PRESERVE,
                fragment_dimensions=(
                    FragmentDimensions.TARGET
                    if self.merge is not None
                    else FragmentDimensions.NOT_APPLICABLE
                ),
                row_count_relation=RowCountRelation.SAME,
                key_relation=KeyRelation.IDENTICAL,
                row_order_relation=RowOrderRelation.PRESERVE,
                existing_data_relation=ExistingDataRelation.PRESERVE,
                dataframe_input_scope=DataFrameInputScope.TARGET,
                feature_input_scope=FeatureInputScope.TARGET,
            )

        relationship_values = set(grain_relationships.values())
        dimension_change: DimensionChange.Value = (
            DimensionChange.ADD
            if GrainRelationship.EXPAND in relationship_values
            else DimensionChange.REMOVE
            if GrainRelationship.COLLAPSE in relationship_values
            else DimensionChange.PRESERVE
            if has_foreign_source
            else DimensionChange.UNRESTRICTED
        )
        return OperatorExecutionContract(
            produces_features=True,
            is_source=True,
            is_transformer=False,
            is_sink=False,
            is_effect=False,
            dimension_change=dimension_change,
            fragment_dimensions=(
                FragmentDimensions.SUBSET
                if dimension_change == DimensionChange.ADD
                else FragmentDimensions.TARGET
            ),
            row_count_relation=RowCountRelation.UNRESTRICTED,
            key_relation=KeyRelation.UNRESTRICTED,
            row_order_relation=RowOrderRelation.UNRESTRICTED,
            existing_data_relation=ExistingDataRelation.UNRESTRICTED,
            dataframe_input_scope=(
                DataFrameInputScope.FOREIGN if has_foreign_source else DataFrameInputScope.NONE
            ),
            feature_input_scope=(
                FeatureInputScope.DATAFRAME if has_foreign_source else FeatureInputScope.NONE
            ),
        )

    def source_details(
        self, spec: Spec, key: OperatorKey
    ) -> tuple[tuple[ProfileKey, ...], OperatorSourceStatus.Value]:
        """Resolve this operator's feature and dataframe sources without hiding ambiguity."""
        source_keys: list[ProfileKey] = []
        unresolved_input = False
        ambiguous_input = False
        for _, owners in spec.input_candidates[key]:
            if not owners:
                unresolved_input = True
            elif len(owners) > 1:
                ambiguous_input = True
                source_keys.extend(owners)
            else:
                source_keys.append(owners[0])

        invalid_reference = False
        for _, _, profile_id in spec.operator_dataframe_arguments[key]:
            if profile_id is None:
                continue
            profile_key = spec.profile_keys.get(profile_id)
            if profile_key is None:
                invalid_reference = True
            else:
                source_keys.append(profile_key)

        unique_sources = tuple(dict.fromkeys(source_keys))
        if invalid_reference:
            return unique_sources, OperatorSourceStatus.INVALID_REFERENCE
        if ambiguous_input or len(unique_sources) > 1:
            return unique_sources, OperatorSourceStatus.AMBIGUOUS
        if unresolved_input:
            return unique_sources, OperatorSourceStatus.MISSING
        if unique_sources:
            return unique_sources, OperatorSourceStatus.RESOLVED
        return (), OperatorSourceStatus.MISSING

    def grain_relationships(
        self, spec: Spec, key: OperatorKey
    ) -> dict[ProfileKey | None, GrainRelationship.Value]:
        """Return this operator's source-to-target grain relationships."""
        sources, status = self.source_details(spec, key)
        target_profile = (
            key[0]
            if self.output_features
            or self.merge is not None
            or spec.profiles_by_key[key[0]].seed == key[1]
            else None
        )
        source_profiles: tuple[ProfileKey | None, ...] = sources
        if not source_profiles:
            if status == OperatorSourceStatus.MISSING and not self.input_features:
                source_profiles = (None,)
            else:
                return {None: GrainRelationship.NOT_APPLICABLE}
        relationships = {
            source: self._grain_relationship(spec, source, target_profile)
            for source in source_profiles
        }
        if sources and status != OperatorSourceStatus.RESOLVED:
            relationships[None] = GrainRelationship.NOT_APPLICABLE
        return relationships

    def profile_resolutions(
        self, spec: Spec, profile_key: ProfileKey
    ) -> tuple[dimension_module.Resolution, ...] | None:
        """Resolve the selected dimension models for a source or target profile."""
        resolutions: list[dimension_module.Resolution] = []
        for grain in spec.profiles_by_key[profile_key].grain:
            dimension = spec.dimensions.get(grain.dimension)
            resolution = (
                dimension.resolutions.get(grain.resolution) if dimension is not None else None
            )
            if resolution is None:
                return None
            resolutions.append(resolution)
        return tuple(resolutions)

    def _grain_relationship(
        self,
        spec: Spec,
        source_profile_key: ProfileKey | None,
        target_profile_key: ProfileKey | None,
    ) -> GrainRelationship.Value:
        """Classify two profile grains using the declared resolution hierarchy."""
        if source_profile_key is None and target_profile_key is None:
            return GrainRelationship.NOT_APPLICABLE
        if source_profile_key is None:
            return GrainRelationship.EMERGE
        if target_profile_key is None:
            return GrainRelationship.VANISH
        source_resolutions = self.profile_resolutions(spec, source_profile_key)
        target_resolutions = self.profile_resolutions(spec, target_profile_key)
        if source_resolutions is None or target_resolutions is None:
            return GrainRelationship.NOT_APPLICABLE
        source_grain = spec.profiles_by_key[source_profile_key].grain_reference_set
        target_grain = spec.profiles_by_key[target_profile_key].grain_reference_set
        if source_grain == target_grain:
            return GrainRelationship.SAME
        if spec.grain_refines(source_profile_key, target_profile_key):
            return GrainRelationship.EXPAND
        if spec.grain_refines(target_profile_key, source_profile_key):
            return GrainRelationship.COLLAPSE
        return GrainRelationship.UNRELATED

    def produces_target_features(self, spec: Spec, key: OperatorKey) -> bool:
        """Return whether this operator computes dataframe outputs from its target dataset."""
        function = spec.functions.get(self.compute.function)
        return (
            self.merge is None
            and function is not None
            and function.returns == arg_types.DATAFRAME
            and any(
                source_profile == key[0]
                for _, _, source_profile in spec.operator_dataframe_arguments[key]
            )
        )

    @functools.cached_property
    def profile_references(self) -> tuple[str, ...]:
        """Return normalized profile IDs in reference order, retaining duplicates."""
        return tuple(
            profile_id
            for profile_id, _ in self.compute.references_by_prefix[selectors.PROFILE_PREFIX]
        )

    @functools.cached_property
    def feature_selectors(self) -> tuple[str, ...]:
        """Return normalized compute feature IDs in reference order, retaining duplicates."""
        return self.compute.feature_references

    @property
    def dimension_reference_paths(self) -> tuple[tuple[str, tuple[str | int, ...]], ...]:
        """Return normalized dimension IDs and relative compute argument paths."""
        return self.compute.references_by_prefix[selectors.DIMENSION_PREFIX]

    @functools.cached_property
    def dimensions_references(self) -> tuple[str, ...]:
        """Return normalized binding dimension IDs in order, retaining duplicates."""
        return tuple(dimension for dimension, _ in self.dimension_reference_paths)


class Grain(base.StrictModel):
    """A selected resolution that contributes keys to a profile's grain."""

    dimension: str
    resolution: str


class Order(Grain):
    """One logical profile ordering key, without a physical row-order guarantee."""

    direction: typing.Literal["asc", "desc"]


class Profile(base.StrictModel):
    """An entry under the top-level ID-keyed `profiles` object."""

    id: str = pydantic.Field(exclude=True)
    name: str | None = None
    description: str | None = None
    category: str | None = None
    scope: str | None = None
    seed: str | None = None
    grain: list[Grain] = pydantic.Field(default_factory=list)
    relations: list[Grain] = pydantic.Field(default_factory=list)
    features: dict[str, Feature] = pydantic.Field(default_factory=dict)
    assembly: dict[str, Operator] = pydantic.Field(default_factory=dict)
    order: list[Order] = pydantic.Field(default_factory=list)

    def identifiers(self, dimensions: typing.Mapping[str, dimension_module.Dimension]) -> list[str]:
        """Return only the selected grain columns identifying profile rows.

        Args:
            dimensions: Dimension catalog from the owning Spec.

        Returns:
            Profile identifier columns in grain order, excluding relations.
        """
        return list(self.identifier_types(dimensions))

    def identifier_types(
        self, dimensions: typing.Mapping[str, dimension_module.Dimension]
    ) -> dict[str, str]:
        """Return logical types for the selected grain identifiers.

        Args:
            dimensions: Dimension catalog from the owning Spec.

        Returns:
            Profile identifier columns mapped to logical types, excluding relations.
        """
        return {
            resolution.key: resolution.type
            for reference in self.grain
            if (dimension := dimensions.get(reference.dimension)) is not None
            and (resolution := dimension.resolutions.get(reference.resolution)) is not None
        }

    def relation_types(
        self, dimensions: typing.Mapping[str, dimension_module.Dimension]
    ) -> dict[str, str]:
        """Return logical types for resolutions relating this profile to other profiles.

        Args:
            dimensions: Dimension catalog from the owning Spec.

        Returns:
            Declared relation columns mapped to logical types, excluding identifiers.
        """
        return {
            resolution.key: resolution.type
            for reference in self.relations
            if (dimension := dimensions.get(reference.dimension)) is not None
            and (resolution := dimension.resolutions.get(reference.resolution)) is not None
        }

    def keys(self, dimensions: typing.Mapping[str, dimension_module.Dimension]) -> list[str]:
        """Return identifiers and relations in declaration order."""
        return list(self.key_types(dimensions))

    def key_types(
        self, dimensions: typing.Mapping[str, dimension_module.Dimension]
    ) -> dict[str, str]:
        """Return logical types for identifiers and relations together."""
        return self.identifier_types(dimensions) | self.relation_types(dimensions)

    @functools.cached_property
    def dimension_ids(self) -> list[str]:
        """Return dimension identifiers in profile key order."""
        return [reference.dimension for reference in self.grain]

    @functools.cached_property
    def dimension_id_set(self) -> frozenset[str]:
        """Return dimension IDs for repeated scope checks."""
        return frozenset(self.dimension_ids)

    @pydantic.model_validator(mode="after")
    def generate_name(self) -> typing.Self:
        """Generate a display name from the profile ID when one is not supplied."""
        if self.name is None:
            self.name = base.humanize_identifier(self.id)
        return self

    @property
    def all_features(self) -> dict[str, Feature]:
        """Return the declared feature metadata for this profile."""
        return self.features

    @functools.cached_property
    def arguments(self) -> dict[tuple[str, str], binding_argument.BindingArgument]:
        """Return compute arguments keyed by operator key and argument name."""
        return {
            (operator_id, name): value
            for operator_id, operator in self.assembly.items()
            for name, value in operator.arguments.items()
        }

    @functools.cached_property
    def feature_producers(self) -> dict[str, tuple[tuple[str, Operator], ...]]:
        """Return all declared output operators per feature, retaining aliases."""
        producers: dict[str, list[tuple[str, Operator]]] = {}
        for operator_id, operator in self.assembly.items():
            for feature_id in operator.output_features:
                producers.setdefault(feature_id, []).append((operator_id, operator))
        return {feature: tuple(operators) for feature, operators in producers.items()}

    @functools.cached_property
    def order_dimensions(self) -> tuple[tuple[str, frozenset[str]], ...]:
        """Return normalized order IDs with preceding keys, retaining duplicates."""
        preceding: set[str] = set()
        items = []
        for key in self.order:
            dimension_id = key.dimension
            items.append((dimension_id, frozenset(preceding)))
            preceding.add(dimension_id)
        return tuple(items)

    @functools.cached_property
    def order_references(self) -> frozenset[str]:
        """Return order dimension references for membership checks."""
        return frozenset(
            f"{selectors.DIMENSION_PREFIX}{dimension_id}"
            for dimension_id, _ in self.order_dimensions
        )

    @functools.cached_property
    def grain_reference_set(self) -> frozenset[tuple[str, str]]:
        """Return selected dimension-resolution identities."""
        return frozenset((item.dimension, item.resolution) for item in self.grain)
