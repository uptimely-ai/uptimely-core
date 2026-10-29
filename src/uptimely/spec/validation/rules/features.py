"""Feature ownership discovery and atomic uniqueness checks."""

from uptimely.spec import model as spec_model

from . import datasets


def feature_owners(spec: spec_model.Spec) -> dict[str, tuple[datasets.DatasetDeclaration, ...]]:
    """Collect non-dimension feature owners without discarding ambiguous declarations."""
    owners: dict[str, list[datasets.DatasetDeclaration]] = {}
    for declaration in datasets.iter_datasets(spec):
        for feature in declaration.dataset.features:
            if feature not in spec.dimensions:
                owners.setdefault(feature, []).append(declaration)
    return {feature: tuple(declarations) for feature, declarations in owners.items()}


def validate_feature_ownership(spec: spec_model.Spec) -> None:
    """Require a unique owner for each non-dimension feature."""
    for feature, owners in feature_owners(spec).items():
        if len(owners) > 1:
            raise ValueError(f"Duplicate feature name: {feature}")
