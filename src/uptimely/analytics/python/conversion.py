"""Convert Python declarations to the analytics document format."""

from __future__ import annotations

import typing
from collections import abc

from .. import catalog
from .. import model as analytics_model
from ..json import codec
from . import dataset as dataset_module
from . import dimension as dimension_module
from . import entity as entity_module

type Datasets = (
    abc.Iterable[dataset_module.Dataset | analytics_model.Dataset]
    | abc.Mapping[str, dataset_module.Dataset | analytics_model.Dataset]
)
type Entities = (
    abc.Iterable[entity_module.Entity | analytics_model.Entity]
    | abc.Mapping[str, entity_module.Entity | analytics_model.Entity]
)
type Dimensions = (
    abc.Iterable[dimension_module.Dimension | analytics_model.Dimension]
    | abc.Mapping[str, dimension_module.Dimension | analytics_model.Dimension]
)
type Functions = (
    analytics_model.FunctionCatalog
    | dict[str, analytics_model.FunctionTemplate | dict[str, typing.Any]]
)


def _values[T](resources: abc.Iterable[T] | abc.Mapping[str, T]) -> list[T]:
    """Normalize resource collections without consuming an iterator twice."""
    return list(resources.values()) if isinstance(resources, abc.Mapping) else list(resources)


def to_dict(
    datasets: Datasets | None = None,
    functions: Functions | None = None,
    name: str | None = None,
    dimensions: Dimensions | None = None,
    *,
    entities: Entities | None = None,
) -> dict[str, typing.Any]:
    """Encode Python declarations using the same codec as JSON file exports."""
    return codec.to_document(to_model(datasets, functions, name, dimensions, entities=entities))


def to_model(
    datasets: Datasets | None = None,
    functions: Functions | None = None,
    name: str | None = None,
    dimensions: Dimensions | None = None,
    *,
    entities: Entities | None = None,
) -> analytics_model.Analytics:
    """Build structural analytics without importing function entrypoints.

    Args:
        datasets: Datasets wrapped in a single entity named after ``name``.
        functions: Explicit function catalog, or infer it from declarations.
        name: Optional analytics display name.
        dimensions: Global dimension declarations.
        entities: Explicit entities, mutually exclusive with ``datasets``.

    Raises:
        ValueError: No declarations were supplied or function definitions conflict.
        TypeError: A resource is not a supported declaration or document model.
    """
    if datasets is not None and entities is not None:
        raise ValueError("Use either 'datasets' or 'entities', not both.")
    dimension_values = _dimensions(dimensions)
    declarations: list[dataset_module.Dataset | analytics_model.Dataset] = []
    if entities is not None:
        entity_values: dict[str, analytics_model.Entity] = {}
        for entity in _values(entities):
            if isinstance(entity, entity_module.Entity):
                declarations.extend(entity.datasets)
                canonical = entity.to_model()
            elif isinstance(entity, analytics_model.Entity):
                declarations.extend(entity.datasets)
                canonical = entity
            else:
                raise TypeError("entities must contain Entity declarations or canonical models")
            entity_values[canonical.id] = canonical
        if not entity_values:
            raise ValueError("At least one entity is required.")
    else:
        declarations = _values(datasets) if datasets is not None else []
        if not declarations:
            raise ValueError("At least one dataset is required.")
        entity_id = name or "entity"
        entity_values = {
            entity_id: analytics_model.Entity(
                id=entity_id,
                name=entity_id,
                dimensions=list(dimension_values.values()),
                datasets=[_dataset(declaration) for declaration in declarations],
            )
        }

    if functions is None:
        functions = analytics_model.FunctionCatalog(
            root=catalog.merge_function_catalogs(
                declaration.function_catalog()
                for declaration in declarations
                if isinstance(declaration, dataset_module.Dataset)
            )
        )
    elif not isinstance(functions, (analytics_model.FunctionCatalog, dict)):
        raise TypeError("functions must be a FunctionCatalog or dictionary")

    return analytics_model.Analytics.model_validate(
        {
            "name": name,
            "source": {"name": "python_api", "generated": True},
            "dimensions": dimension_values,
            "functions": functions,
            "entities": entity_values,
        }
    )


def _dataset(
    declaration: dataset_module.Dataset | analytics_model.Dataset,
) -> analytics_model.Dataset:
    """Convert one dataset without accepting entity declarations in its place."""
    if isinstance(declaration, dataset_module.Dataset):
        return declaration.to_model()
    if isinstance(declaration, analytics_model.Dataset):
        return declaration
    raise TypeError("datasets must contain Dataset declarations or canonical models")


def _dimensions(resources: Dimensions | None) -> dict[str, analytics_model.Dimension]:
    """Convert global dimensions, retaining explicitly supplied mapping keys."""
    if resources is None:
        return {}
    if isinstance(resources, abc.Mapping):
        keyed = resources
    else:
        canonical = [_dimension(resource) for resource in resources]
        return {resource.id: resource for resource in canonical}
    dimensions: dict[str, analytics_model.Dimension] = {}
    for identifier, declaration in keyed.items():
        dimensions[identifier] = _dimension(declaration)
    return dimensions


def _dimension(
    declaration: dimension_module.Dimension | analytics_model.Dimension,
) -> analytics_model.Dimension:
    """Convert a dimension or report an explicit invalid-declaration error."""
    if isinstance(declaration, dimension_module.Dimension):
        return declaration.to_model()
    if isinstance(declaration, analytics_model.Dimension):
        return declaration
    raise TypeError("dimensions must contain Dimension declarations or canonical models")
