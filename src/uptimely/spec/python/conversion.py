"""Convert Python declarations to the spec document format."""

from __future__ import annotations

import logging
import typing
from collections import abc

from .. import catalog
from .. import model as spec_model
from ..json import codec
from . import dimension as dimension_module
from . import profile as profile_module

logger = logging.getLogger(__name__)

type Profiles = (
    abc.Iterable[profile_module.Profile | spec_model.Profile]
    | abc.Mapping[str, profile_module.Profile | spec_model.Profile]
)
type Dimensions = (
    abc.Iterable[dimension_module.Dimension | spec_model.Dimension]
    | abc.Mapping[str, dimension_module.Dimension | spec_model.Dimension]
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
    dimensions: Dimensions | None = None,
) -> dict[str, typing.Any]:
    """Encode Python declarations using the same codec as JSON file exports."""
    return codec.to_document(to_model(profiles, functions, name, dimensions))


def to_model(
    profiles: Profiles | None = None,
    functions: Functions | None = None,
    name: str | None = None,
    dimensions: Dimensions | None = None,
) -> spec_model.Spec:
    """Build structural spec without importing function entrypoints.

    Args:
        profiles: Profile declarations keyed by their globally unique IDs.
        functions: Explicit function catalog, or infer it from declarations.
        name: Optional spec display name.
        dimensions: Global dimension declarations.

    Raises:
        ValueError: No declarations were supplied or function definitions conflict.
        TypeError: A resource is not a supported declaration or document model.
    """
    dimension_values = _dimensions(dimensions)
    declarations = _values(profiles) if profiles is not None else []
    if not declarations:
        raise ValueError("At least one profile is required.")

    profile_values: dict[str, spec_model.Profile] = {}
    for declaration in declarations:
        if isinstance(declaration, profile_module.Profile):
            canonical = declaration.to_model(
                dimensions=_profile_dimensions(declaration, dimension_values)
            )
        elif isinstance(declaration, spec_model.Profile):
            canonical = declaration
        else:
            raise TypeError("profiles must contain Profile declarations or canonical models")
        if canonical.id in profile_values:
            raise ValueError(f"Duplicate profile id {canonical.id}")
        profile_values[canonical.id] = canonical

    if logger.isEnabledFor(logging.DEBUG):
        action_count = sum(
            len(declaration.producers) + len(declaration.publishers) + len(declaration.pipelines)
            for declaration in declarations
            if isinstance(declaration, profile_module.Profile)
        )
        logger.debug(
            "\nPython spec validation:\n  - checked output references for %d actions",
            action_count,
        )

    if functions is None:
        functions = spec_model.FunctionCatalog(
            root=catalog.merge_function_catalogs(
                declaration.function_catalog()
                for declaration in declarations
                if isinstance(declaration, profile_module.Profile)
            )
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


def _dimensions(resources: Dimensions | None) -> dict[str, spec_model.Dimension]:
    """Convert global dimensions, retaining explicitly supplied mapping keys."""
    if resources is None:
        return {}
    if isinstance(resources, abc.Mapping):
        keyed = resources
    else:
        canonical = [_dimension(resource) for resource in resources]
        return {resource.id: resource for resource in canonical}
    dimensions: dict[str, spec_model.Dimension] = {}
    for identifier, declaration in keyed.items():
        dimensions[identifier] = _dimension(declaration)
    return dimensions


def _dimension(
    declaration: dimension_module.Dimension | spec_model.Dimension,
) -> spec_model.Dimension:
    """Convert a dimension or report an explicit invalid-declaration error."""
    if isinstance(declaration, dimension_module.Dimension):
        return declaration.to_model()
    if isinstance(declaration, spec_model.Dimension):
        return declaration
    raise TypeError("dimensions must contain Dimension declarations or canonical models")


def _profile_dimensions(
    declaration: profile_module.Profile,
    dimensions: dict[str, spec_model.Dimension],
) -> list[dimension_module.Dimension]:
    """Resolve profile dimension references against the global declarations."""
    resolved: list[dimension_module.Dimension] = []
    for item in declaration.dimensions:
        if not isinstance(item, (str, dimension_module.Dimension)):
            raise TypeError("profile dimensions must contain dimension IDs or declarations")
        identifier = item if isinstance(item, str) else item.id
        if identifier not in dimensions:
            raise ValueError(
                f"Profile '{declaration.id}' references undeclared dimension '{identifier}'"
            )
        if not isinstance(item, str):
            if item.to_model() != dimensions[identifier]:
                raise ValueError(f"Conflicting metadata for dimension '{identifier}'")
            resolved.append(item)
            continue
        model_dimension = dimensions[identifier]
        resolved.append(
            dimension_module.Dimension(
                id=model_dimension.id,
                name=model_dimension.name,
                description=model_dimension.description,
                type=model_dimension.type,
                parent=model_dimension.parent,
            )
        )
    return resolved
