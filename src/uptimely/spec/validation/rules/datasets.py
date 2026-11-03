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
    """Require each order resolution to be selected by the profile grain."""
    logger.debug("    - checking profile order resolutions are selected by each profile")
    for _, profile in spec.profile_items:
        for index, order in enumerate(profile.order):
            if (order.dimension, order.resolution) not in profile.grain_reference_set:
                raise errors.SpecError(
                    f"Profile {profile.id} order references a resolution not selected "
                    "by its grain: "
                    f"{order.dimension}.{order.resolution}",
                    code="invalid_order_resolution",
                    path=("profiles", profile.id, "order", index),
                )


def validate_unique_order_dimension(spec: spec_model.Spec) -> None:
    """Reject repeated profile order resolutions."""
    logger.debug("    - checking profile order resolutions are unique")
    for profile_id, profile in spec.profile_items:
        for index, (dimension, preceding) in enumerate(profile.order_dimensions):
            if dimension in preceding:
                raise errors.SpecError(
                    f"Profile {profile.id} order repeats dimension: {dimension}",
                    code="duplicate_order_resolution",
                    path=("profiles", profile_id, "order", index),
                )
