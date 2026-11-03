"""Atomic profile grain checks."""

import logging

from uptimely.spec import model as spec_model
from uptimely.spec.validation import errors

logger = logging.getLogger(__name__)


def validate_grain_dimensions(spec: spec_model.Spec) -> None:
    """Require profile grain references to name declared dimensions."""
    logger.debug("    - checking profile grain dimension references")
    for profile_id, profile in spec.profile_items:
        for index, reference in enumerate(profile.grain):
            if reference.dimension not in spec.dimensions:
                raise errors.SpecError(
                    f"Profile {profile_id} grain references unknown dimension: "
                    f"{reference.dimension}",
                    code="unknown_grain_dimension",
                    path=("profiles", profile_id, "grain", index, "dimension"),
                )


def validate_unique_grain_dimensions(spec: spec_model.Spec) -> None:
    """Require each profile grain to select at most one resolution per dimension."""
    logger.debug("    - checking profile grain dimension uniqueness")
    for profile_id, profile in spec.profile_items:
        seen: set[str] = set()
        for index, reference in enumerate(profile.grain):
            if reference.dimension in seen:
                raise errors.SpecError(
                    f"Profile {profile_id} grain repeats dimension: {reference.dimension}",
                    code="duplicate_grain_dimension",
                    path=("profiles", profile_id, "grain", index, "dimension"),
                )
            seen.add(reference.dimension)


def validate_grain_resolutions(spec: spec_model.Spec) -> None:
    """Require profile grain references to name resolutions of their dimensions."""
    logger.debug("    - checking profile grain resolution references")
    for profile_id, profile in spec.profile_items:
        for index, reference in enumerate(profile.grain):
            dimension = spec.dimensions[reference.dimension]
            if reference.resolution not in dimension.resolutions:
                raise errors.SpecError(
                    f"Profile {profile_id} grain references unknown resolution "
                    f"{reference.resolution} for dimension {reference.dimension}",
                    code="unknown_grain_resolution",
                    path=("profiles", profile_id, "grain", index, "resolution"),
                )


def validate_unique_grain_keys(spec: spec_model.Spec) -> None:
    """Require profile grain resolutions to use distinct dataframe key columns."""
    logger.debug("    - checking profile grain dataframe keys are unique")
    for profile_id, profile in spec.profile_items:
        seen: set[str] = set()
        for index, reference in enumerate(profile.grain):
            dimension = spec.dimensions[reference.dimension]
            resolution = dimension.resolutions[reference.resolution]
            if resolution.key in seen:
                raise errors.SpecError(
                    f"Profile {profile_id} grain repeats dataframe key: {resolution.key}",
                    code="duplicate_grain_key",
                    path=("profiles", profile_id, "grain", index, "resolution"),
                )
            seen.add(resolution.key)
