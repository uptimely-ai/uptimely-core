"""Feature selection normalization for project builds and manifests."""

from __future__ import annotations

from collections.abc import Collection

FeatureSelection = Collection[str] | None


def normalize_features(features: object) -> list[str] | None:
    """Validate and normalize an optional nonempty feature selection."""
    if features is None:
        return None
    if isinstance(features, str) or not isinstance(features, Collection):
        raise ValueError("features must be a collection of feature identifiers")
    if not features:
        raise ValueError("features must select at least one output feature (a nonempty list)")
    feature_names: list[str] = []
    for feature in features:
        if not isinstance(feature, str) or not feature.strip():
            raise ValueError("feature identifiers must be nonempty strings")
        feature_names.append(feature)
    return sorted(set(feature_names))
