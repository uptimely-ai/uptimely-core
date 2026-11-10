"""Convert Python declarations to the spec document format."""

from __future__ import annotations

import logging
import typing
from collections import abc

from .. import model as spec_model
from .. import selectors, serialization
from . import profile as profile_module

logger = logging.getLogger(__name__)

type Profiles = (
    abc.Iterable[profile_module.Profile | spec_model.Profile]
    | abc.Mapping[str, profile_module.Profile | spec_model.Profile]
)
type Functions = (
    spec_model.FunctionCatalog | dict[str, spec_model.FunctionTemplate | dict[str, typing.Any]]
)


def _values[T](resources: abc.Iterable[T] | abc.Mapping[str, T]) -> list[T]:
    """Normalize resource collections without consuming an iterator twice."""
    return list(resources.values()) if isinstance(resources, abc.Mapping) else list(resources)


def to_dict(
    profiles: Profiles | None = None,
    functions: Functions | None = None,
    name: str | None = None,
) -> dict[str, typing.Any]:
    """Encode Python declarations using the same serializer as JSON file exports."""
    return serialization.to_document(to_model(profiles, functions, name))


def to_model(
    profiles: Profiles | None = None,
    functions: Functions | None = None,
    name: str | None = None,
) -> spec_model.Spec:
    """Build structural spec without importing function entrypoints.

    Args:
        profiles: Profile declarations keyed by their globally unique IDs.
        functions: Explicit function catalog, or infer it from declarations.
        name: Optional spec display name.

    Raises:
        ValueError: No declarations were supplied or function definitions conflict.
        TypeError: A resource is not a supported declaration or document model.
    """
    declarations = _values(profiles) if profiles is not None else []
    if not declarations:
        raise ValueError("At least one profile is required.")

    profile_values: dict[str, spec_model.Profile] = {}
    dimension_values: dict[str, spec_model.Dimension] = {}
    for declaration in declarations:
        if isinstance(declaration, profile_module.Profile):
            canonical = declaration.to_model()
            for item in (*declaration.grain, *declaration.relations):
                dimension_declaration = item.dimension
                if dimension_declaration is None:
                    raise ValueError(
                        f"Profile '{declaration.id}' grain and relation resolutions "
                        "must be selected through Dimension.resolution()"
                    )
                dimension = dimension_declaration.to_model()
                existing = dimension_values.get(dimension.id)
                if existing is not None and existing != dimension:
                    raise ValueError(f"Conflicting metadata for dimension '{dimension.id}'")
                dimension_values.setdefault(dimension.id, dimension)
        elif isinstance(declaration, spec_model.Profile):
            canonical = declaration
            if canonical.grain or canonical.relations:
                raise ValueError(
                    f"Profile '{canonical.id}' has grain or relation references but no dimension "
                    "declarations to infer"
                )
        else:
            raise TypeError("profiles must contain Profile declarations or canonical models")
        if canonical.id in profile_values:
            raise ValueError(f"Duplicate profile id {canonical.id}")
        profile_values[canonical.id] = canonical

    if logger.isEnabledFor(logging.DEBUG):
        operator_count = sum(
            len(declaration.assembly)
            for declaration in declarations
            if isinstance(declaration, profile_module.Profile)
        )
        logger.debug(
            "Collected feature interfaces for %d operators",
            operator_count,
        )

    if functions is None:
        functions = spec_model.FunctionCatalog.merge(
            declaration.function_catalog()
            for declaration in declarations
            if isinstance(declaration, profile_module.Profile)
        )
    elif not isinstance(functions, (spec_model.FunctionCatalog, dict)):
        raise TypeError("functions must be a FunctionCatalog or dictionary")

    document = spec_model.Spec.model_validate(
        {
            "name": name,
            "source": {"name": "python_api", "generated": True},
            "dimensions": dimension_values,
            "functions": functions,
            "profiles": profile_values,
        }
    )
    for declaration in declarations:
        if not isinstance(declaration, profile_module.Profile):
            continue
        for operator in declaration._assembly_by_id.values():
            if operator.interface.inputs is None:
                interface = document.profiles[declaration.id].assembly[operator.id].interface
                interface.inputs = [
                    reference
                    for reference in interface.inputs
                    if reference.removeprefix(selectors.FEATURE_PREFIX) not in document.key_ids
                ]
    return document
