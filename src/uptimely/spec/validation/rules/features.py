"""Feature ownership discovery and atomic uniqueness checks."""

from uptimely.spec import model as spec_model


def validate_feature_ownership(spec: spec_model.Spec) -> None:
    """Require a unique owner for each non-dimension feature."""
    for feature, owners in spec.feature_owners.items():
        if len(owners) > 1:
            raise ValueError(f"Duplicate feature name: {feature}")
