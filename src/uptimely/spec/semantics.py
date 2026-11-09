"""Derived operator relationships from Spec declarations."""

from __future__ import annotations

import functools
import typing

from .model.dimension import Resolution
from .model.spec import OperatorKey, ProfileKey, Spec

type OperatorExecutionForm = typing.Literal["compute", "compute + merge"]
type BindingRole = typing.Literal["compute", "merge"]
type OperatorSourceStatus = typing.Literal["resolved", "missing", "ambiguous", "invalid_reference"]
type GrainRelationship = typing.Literal["same", "expand", "collapse", "unrelated", "not_applicable"]


class Semantics:
    """Derive operator relationships from an authoritative Spec."""

    def __init__(self, spec: Spec) -> None:
        """Create a semantic view over a structurally parsed Spec."""
        self.spec = spec

    @functools.cached_property
    def operator_execution_forms(self) -> dict[OperatorKey, OperatorExecutionForm]:
        """Return whether each operator declares compute alone or compute and merge."""
        return {
            key: "compute + merge" if operator.merge is not None else "compute"
            for key, operator in self.spec.operator_items
        }

    @functools.cached_property
    def operator_binding_roles(self) -> dict[OperatorKey, tuple[BindingRole, ...]]:
        """Return the compute and optional merge roles declared by each operator."""
        return {key: tuple(operator.bindings) for key, operator in self.spec.operator_items}

    @functools.cached_property
    def operator_source_profile_keys(
        self,
    ) -> dict[OperatorKey, tuple[ProfileKey, ...]]:
        """Return known source profiles for each operator, retaining ambiguous candidates."""
        return {key: details[0] for key, details in self._operator_source_details_by_key.items()}

    @functools.cached_property
    def operator_source_statuses(
        self,
    ) -> dict[OperatorKey, OperatorSourceStatus]:
        """Return whether each operator's source is resolved, missing, or ambiguous."""
        return {key: details[1] for key, details in self._operator_source_details_by_key.items()}

    @functools.cached_property
    def _operator_source_details_by_key(
        self,
    ) -> dict[
        OperatorKey,
        tuple[tuple[ProfileKey, ...], OperatorSourceStatus],
    ]:
        """Resolve source profiles and their status once for each operator."""
        return {key: self._operator_source_details(key) for key, _ in self.spec.operator_items}

    @functools.cached_property
    def operator_source_resolutions(
        self,
    ) -> dict[
        OperatorKey,
        dict[ProfileKey, tuple[Resolution, ...] | None],
    ]:
        """Return selected dimension resolutions for every known source profile."""
        return {
            key: {
                source: self._profile_resolutions(source)
                for source in self.operator_source_profile_keys[key]
            }
            for key, _ in self.spec.operator_items
        }

    @functools.cached_property
    def operator_target_resolutions(
        self,
    ) -> dict[OperatorKey, tuple[Resolution, ...] | None]:
        """Return selected dimension resolutions for each operator's target profile."""
        return {key: self._profile_resolutions(key[0]) for key, _ in self.spec.operator_items}

    @functools.cached_property
    def operator_grain_relationships(
        self,
    ) -> dict[OperatorKey, dict[ProfileKey | None, GrainRelationship]]:
        """Return grain relationships to known sources, or not-applicable if unresolved."""
        return {
            key: (
                {
                    source: self._grain_relationship(source, key[0])
                    for source in self.operator_source_profile_keys[key]
                }
                | (
                    {None: "not_applicable"}
                    if self.operator_source_statuses[key] != "resolved"
                    else {}
                )
            )
            for key, _ in self.spec.operator_items
        }

    def _operator_source_details(
        self, key: OperatorKey
    ) -> tuple[tuple[ProfileKey, ...], OperatorSourceStatus]:
        """Resolve feature and dataframe sources without hiding ambiguity."""
        source_keys: list[ProfileKey] = []
        unresolved_input = False
        ambiguous_input = False
        for _, owners in self.spec.input_candidates[key]:
            if not owners:
                unresolved_input = True
            elif len(owners) > 1:
                ambiguous_input = True
                source_keys.extend(owners)
            else:
                source_keys.append(owners[0])

        invalid_reference = False
        for _, _, profile_id in self.spec.operator_dataframe_arguments[key]:
            if profile_id is None:
                continue
            profile_key = self.spec.profile_keys.get(profile_id)
            if profile_key is None:
                invalid_reference = True
            else:
                source_keys.append(profile_key)

        unique_sources = tuple(dict.fromkeys(source_keys))
        if invalid_reference:
            return unique_sources, "invalid_reference"
        if ambiguous_input or len(unique_sources) > 1:
            return unique_sources, "ambiguous"
        if unresolved_input:
            return unique_sources, "missing"
        if unique_sources:
            return unique_sources, "resolved"
        return (), "missing"

    def _grain_relationship(
        self, source_profile_key: ProfileKey, target_profile_key: ProfileKey
    ) -> GrainRelationship:
        """Classify two profile grains using the declared resolution hierarchy."""
        source = self.spec.profiles_by_key[source_profile_key]
        target = self.spec.profiles_by_key[target_profile_key]
        if (
            self._profile_resolutions(source_profile_key) is None
            or self._profile_resolutions(target_profile_key) is None
        ):
            return "not_applicable"
        source_grain = source.grain_reference_set
        target_grain = target.grain_reference_set
        if source_grain == target_grain:
            return "same"
        if self.spec.grain_refines(source_profile_key, target_profile_key):
            return "expand"
        if self.spec.grain_refines(target_profile_key, source_profile_key):
            return "collapse"
        return "unrelated"

    def _profile_resolutions(self, profile_key: ProfileKey) -> tuple[Resolution, ...] | None:
        """Resolve a profile's selected dimension-resolution models."""
        resolutions: list[Resolution] = []
        for grain in self.spec.profiles_by_key[profile_key].grain:
            dimension = self.spec.dimensions.get(grain.dimension)
            resolution = (
                dimension.resolutions.get(grain.resolution) if dimension is not None else None
            )
            if resolution is None:
                return None
            resolutions.append(resolution)
        return tuple(resolutions)
