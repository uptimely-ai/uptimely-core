"""Convert Python declarations to the spec document format."""

from __future__ import annotations

import logging
import typing
from collections import abc

from .. import model as spec_model
from ..json import codec
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
    """Encode Python declarations using the same codec as JSON file exports."""
    return codec.to_document(to_model(profiles, functions, name))


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
            for item in declaration.grain:
                dimension = item.dimension.to_model()
                existing = dimension_values.get(dimension.id)
                if existing is not None and existing != dimension:
                    raise ValueError(f"Conflicting metadata for dimension '{dimension.id}'")
                dimension_values.setdefault(dimension.id, dimension)
        elif isinstance(declaration, spec_model.Profile):
            canonical = declaration
            if canonical.grain:
                raise ValueError(
                    f"Profile '{canonical.id}' has grain references but no dimension "
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
            "\nPython spec validation:\n  - collected feature interfaces for %d operators",
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

    return spec_model.Spec.model_validate(
        {
            "name": name,
            "source": {"name": "python_api", "generated": True},
            "dimensions": dimension_values,
            "functions": functions,
            "profiles": profile_values,
        }
    )
