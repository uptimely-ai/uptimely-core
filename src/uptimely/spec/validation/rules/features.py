"""Feature ownership discovery and atomic uniqueness checks."""

import logging

from uptimely.spec import model as spec_model

logger = logging.getLogger(__name__)


def validate_feature_ownership(spec: spec_model.Spec) -> None:
    """Require a unique owner for each non-dimension feature."""
    logger.debug("    - checking unique ownership of non-dimension features")
    for feature, owners in spec.feature_owners.items():
        if len(owners) > 1:
            raise ValueError(f"Duplicate feature name: {feature}")
