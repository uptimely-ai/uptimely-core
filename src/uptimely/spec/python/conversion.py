"""Convert Python declarations to the spec document format."""

from __future__ import annotations

import logging
import typing
from collections import abc

from .. import model as spec_model
from .. import selectors, serialization
from . import profile as profile_module

logger = logging.getLogger(__name__)

_PYTHON_SOURCE_NAME = "python_api"
_PYTHON_SOURCE_GENERATED = True

type Functions = (
    spec_model.FunctionCatalog | dict[str, spec_model.FunctionTemplate | dict[str, typing.Any]]
)


def _profile_registry(
    profiles: abc.Sequence[profile_module.Profile],
) -> dict[str, spec_model.Profile]:
    """Convert profiles to an ID-keyed registry without overwriting duplicates."""
    models: dict[str, spec_model.Profile] = {}
    for profile in profiles:
        if not isinstance(profile, profile_module.Profile):
            raise TypeError("profiles must contain Profile declarations")
        model = profile.to_model()
        if model.id in models:
            raise ValueError(f"Duplicate profile id {model.id}")
        models[model.id] = model
    return models


def _dimension_registry(
    profiles: abc.Sequence[profile_module.Profile],
) -> dict[str, spec_model.Dimension]:
    """Collect dimensions referenced by profile grains and relations."""
    dimensions: dict[str, spec_model.Dimension] = {}
    for profile in profiles:
        # Relations can reference dimensions not used by any profile's grain.
        for resolution in (*profile.grain, *profile.relations):
            dimension, _ = profile._selected_resolution(resolution)
            dimension_model = dimension.to_model()
            existing = dimensions.setdefault(dimension_model.id, dimension_model)
            if existing != dimension_model:
                raise ValueError(f"Conflicting metadata for dimension '{dimension_model.id}'")
    return dimensions


def _remove_key_inputs(
    profiles: abc.Sequence[profile_module.Profile],
    profile_models: abc.Mapping[str, spec_model.Profile],
    dimensions: abc.Mapping[str, spec_model.Dimension],
) -> None:
    """Remove inferred feature inputs whose names match Spec keys.

    This handles key columns passed through ``ref.feature``. Dimension
    resolution key selectors do not create inferred feature inputs.
    """
    key_ids = {key for profile in profile_models.values() for key in profile.keys(dimensions)}
    for profile in profiles:
        for operator in profile._assembly_by_id.values():
            if operator.inputs is None:
                interface = profile_models[profile.id].assembly[operator.id].interface
                interface.inputs = [
                    reference
                    for reference in interface.inputs
                    if reference.removeprefix(selectors.FEATURE_PREFIX) not in key_ids
                ]


def to_dict(
    profiles: abc.Sequence[profile_module.Profile] | None = None,
    functions: Functions | None = None,
    name: str | None = None,
) -> dict[str, typing.Any]:
    """Encode Python declarations using the same serializer as JSON file exports."""
    return serialization.to_document(to_model(profiles, functions, name))


def to_model(
    profiles: abc.Sequence[profile_module.Profile] | None = None,
    functions: Functions | None = None,
    name: str | None = None,
) -> spec_model.Spec:
    """Build structural spec without importing function entrypoints.

    Args:
        profiles: A sequence of profile declarations with globally unique IDs.
        functions: Explicit function catalog, or infer it from declarations.
        name: Optional spec display name.

    Raises:
        ValueError: No declarations were supplied or function definitions conflict.
        TypeError: Profiles is not a sequence of Python profile declarations.
    """
    if profiles is not None and not isinstance(profiles, abc.Sequence):
        raise TypeError("profiles must be a sequence of Profile declarations")
    if not profiles:
        raise ValueError("At least one profile is required.")
    profile_values = _profile_registry(profiles)
    dimension_values = _dimension_registry(profiles)

    if logger.isEnabledFor(logging.DEBUG):
        operator_count = sum(len(profile.assembly) for profile in profiles)
        logger.debug(
            "Collected feature interfaces for %d operators",
            operator_count,
        )

    if functions is None:
        functions = spec_model.FunctionCatalog.merge(
            profile.function_catalog() for profile in profiles
        )
    elif not isinstance(functions, (spec_model.FunctionCatalog, dict)):
        raise TypeError("functions must be a FunctionCatalog or dictionary")

    _remove_key_inputs(profiles, profile_values, dimension_values)
    return spec_model.Spec.model_validate(
        {
            "name": name,
            "source": {"name": _PYTHON_SOURCE_NAME, "generated": _PYTHON_SOURCE_GENERATED},
            "dimensions": dimension_values,
            "functions": functions,
            "profiles": profile_values,
        }
    )
