"""Atomic profile dimension-membership checks."""

import logging

from uptimely.spec import model as spec_model

logger = logging.getLogger(__name__)


def validate_profile_dimensions(spec: spec_model.Spec) -> None:
    """Require each profile's dimensions to be declared globally."""
    logger.debug("    - checking profile dimension references")
    dimension_ids = frozenset(spec.dimensions)
    for profile_id, profile in spec.profile_items:
        dimensions = profile.dimension_id_set
        if not dimensions.issubset(dimension_ids):
            raise ValueError(
                f"Profile {profile_id} references unknown dimensions: "
                + ", ".join(sorted(dimensions - dimension_ids))
            )
