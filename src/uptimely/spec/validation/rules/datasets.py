"""Atomic dataset identity and ordering checks."""

import logging

from uptimely.spec import model as spec_model
from uptimely.spec.validation import errors

logger = logging.getLogger(__name__)


def validate_profile_ids(spec: spec_model.Spec) -> None:
    """Require globally unique profile IDs."""
    logger.debug("    - checking globally unique profile IDs")
    seen: set[str] = set()
    for profile_id, profile in spec.profile_items:
        if profile_id != profile.id:
            raise errors.SpecError(
                f"Profile key {profile_id} does not match profile id {profile.id}",
                code="invalid_profile_id",
                path=("profiles", profile_id),
            )
        if profile.id in seen:
            raise errors.SpecError(
                f"Duplicate profile id {profile.id}",
                code="duplicate_profile_id",
                path=("profiles", profile.id),
            )
        seen.add(profile.id)


def validate_order_dimension(spec: spec_model.Spec) -> None:
    """Require each order dimension to be declared by its profile."""
    logger.debug("    - checking profile order dimensions are declared by each profile")
    for profile_id, profile in spec.profile_items:
        for index, (dimension, _) in enumerate(profile.order_dimensions):
            if dimension not in spec.dimensions_by_profile[profile_id]:
                raise errors.SpecError(
                    f"Profile {profile.id} order references an undeclared dimension: {dimension}",
                    code="invalid_order_dimension",
                    path=("profiles", profile.id, "order", index, "dimension"),
                )


def validate_unique_order_dimension(spec: spec_model.Spec) -> None:
    """Reject a repeated order dimension."""
    logger.debug("    - checking dataset order dimensions are unique")
    for profile_id, profile in spec.profile_items:
        for index, (dimension, preceding) in enumerate(profile.order_dimensions):
            if dimension in preceding:
                raise errors.SpecError(
                    f"Profile {profile.id} order repeats dimension: {dimension}",
                    code="duplicate_order_dimension",
                    path=("profiles", profile_id, "order", index, "dimension"),
                )
