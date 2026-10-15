from __future__ import annotations

import typing

import pydantic

from ..python import bind
from . import json_model


def _argument_metadata(argument: typing.Any) -> dict[str, typing.Any]:
    """Serialize an argument definition."""
    return {"type": argument.type, "comment": argument.comment}


def python_to_spec_dict(
    datasets: object | None = None,
    functions: typing.Any = None,
    name: str | None = None,
    dimensions: dict[str, json_model.Dimension] | list[json_model.Dimension] | None = None,
    *,
    entities: object | None = None,
) -> dict[str, typing.Any]:
    """Convert Python authoring models into the canonical JSON dialect."""
    if entities is not None:
        if datasets is not None:
            raise ValueError("Use either 'datasets' or 'entities', not both.")
        declarations = list(entities.values()) if isinstance(entities, dict) else list(entities)
        if not declarations:
            raise ValueError("At least one entity is required.")
        entity_values = {entity.id: entity.to_model() for entity in declarations}
        dataset_values = {
            dataset.id: dataset for entity in entity_values.values() for dataset in entity.datasets
        }
    else:
        declarations = (
            list(datasets.values()) if isinstance(datasets, dict) else list(datasets or [])
        )
        if not declarations:
            raise ValueError("At least one dataset is required.")
        if all(hasattr(declaration, "datasets") for declaration in declarations):
            entity_values = {entity.id: entity.to_model() for entity in declarations}
            dataset_values = {
                dataset.id: dataset
                for entity in entity_values.values()
                for dataset in entity.datasets
            }
        else:
            dataset_values = {
                str(index): declaration.to_model()
                if hasattr(declaration, "to_model")
                else declaration
                for index, declaration in enumerate(declarations)
            }
            entity_values = None

    if not all(isinstance(dataset, pydantic.BaseModel) for dataset in dataset_values.values()):
        raise TypeError("datasets must contain Pydantic models")

    resolved_functions = functions
    if resolved_functions is None:
        resolved_functions = _auto_function_catalog(declarations)

    return _static_datasets_to_spec(
        dataset_values,
        name,
        resolved_functions,
        _resources_by_id(dimensions),
        entity_values,
    )


def _resources_by_id(
    resources: dict[str, typing.Any] | list[typing.Any] | None,
) -> dict[str, typing.Any]:
    """Normalize Python resource declarations to their canonical ID-keyed form."""
    if resources is None:
        return {}
    resource_map = (
        resources
        if isinstance(resources, dict)
        else {resource.id: resource for resource in resources}
    )
    return {
        identifier: resource.to_model() if hasattr(resource, "to_model") else resource
        for identifier, resource in resource_map.items()
    }


def _configured_entrypoint(
    functions: typing.Any, category: str, function_name: str, fallback: str
) -> str:
    """Return the configured entrypoint or the declared fallback."""
    if isinstance(functions, pydantic.BaseModel):
        lookup = getattr(functions, category, {})
    elif isinstance(functions, dict):
        lookup = functions.get(category, {})
    else:
        lookup = {}

    if isinstance(lookup, dict):
        configured = lookup.get(function_name)
        if isinstance(configured, pydantic.BaseModel):
            return str(configured.entrypoint)
        if isinstance(configured, dict):
            entrypoint = configured.get("entrypoint")
            if entrypoint:
                return str(entrypoint)
    return fallback


def _configured_function(functions: typing.Any, category: str, function_name: str) -> typing.Any:
    """Return a configured function model or mapping entry, when available."""
    if isinstance(functions, pydantic.BaseModel):
        lookup = getattr(functions, category, {})
        return lookup.get(function_name) if isinstance(lookup, dict) else None
    if isinstance(functions, dict):
        lookup = functions.get(category, {})
        return lookup.get(function_name) if isinstance(lookup, dict) else None
    return None


def _auto_function_catalog(declarations: object) -> dict[str, typing.Any]:
    """Build an automatic function catalog from original Python declarations."""
    merged: dict[str, dict[str, typing.Any]] = {
        "read": {},
        "write": {},
        "vectorize": {},
        "collapse": {},
        "expand": {},
        "conform": {},
    }

    declaration_list = (
        list(declarations.values()) if isinstance(declarations, dict) else list(declarations or [])
    )

    def register_dataset(dataset: typing.Any) -> None:
        for category, functions in dataset.function_catalog().model_dump().items():
            for function_id, function in functions.items():
                existing = merged[category].get(function_id)
                if existing is not None and existing["entrypoint"] != function["entrypoint"]:
                    raise ValueError(f"Conflicting function id '{function_id}' for {category}")
                merged[category][function_id] = function

    for declaration in declaration_list:
        if hasattr(declaration, "datasets"):
            for dataset in getattr(declaration, "datasets", []) or []:
                register_dataset(dataset)
        elif hasattr(declaration, "mappings"):
            register_dataset(declaration)

    return merged


def _static_datasets_to_spec(
    datasets: dict[str, pydantic.BaseModel],
    name: str | None,
    functions: dict[str, typing.Any],
    dimensions: dict[str, json_model.Dimension],
    entities: dict[str, pydantic.BaseModel] | None = None,
) -> dict[str, typing.Any]:
    """Convert specification-layer dataset models into a specification."""
    entity_id = name or "entity"
    dataset_entries: list[dict[str, typing.Any]] = []

    for dataset in datasets.values():
        entry = dataset.model_dump(exclude_none=False)
        entry["id"] = dataset.id
        dataset_entries.append(entry)

    if entities is None:
        entity_values = {
            name or "entity": {
                "name": name or "entity",
                "dimensions": list(dimensions),
                "datasets": dataset_entries,
            }
        }
    else:
        entity_values = {}
        for entity_id, entity in entities.items():
            entity_value = entity.model_dump(exclude_none=False)
            entity_value["id"] = entity_id
            entity_value["datasets"] = [
                {**dataset.model_dump(exclude_none=False), "id": dataset.id}
                for dataset in entity.datasets
            ]
            entity_values[entity_id] = entity_value

    return {
        **({"name": name} if name is not None else {}),
        "version": "0.1.0",
        "source": {"name": "python_api", "generated": True},
        "dimensions": {
            identifier: resource.model_dump(exclude_none=False)
            for identifier, resource in dimensions.items()
        },
        "functions": {
            "read": _static_function_catalog(datasets, functions, "read"),
            "write": _static_function_catalog(datasets, functions, "write"),
            "vectorize": {
                **_static_function_catalog(datasets, functions, "vectorize"),
            },
            "collapse": _static_function_catalog(datasets, functions, "collapse"),
            "expand": _static_function_catalog(datasets, functions, "expand"),
            "conform": _static_function_catalog(datasets, functions, "conform"),
        },
        "entities": entity_values,
    }


def _static_function_catalog(
    datasets: dict[str, pydantic.BaseModel], functions: dict[str, typing.Any], category: str
) -> dict[str, typing.Any]:
    """Build the function catalog for a given operation category."""
    catalog: dict[str, typing.Any] = {}
    if isinstance(functions, pydantic.BaseModel):
        by_category = getattr(functions, category, {})
        if isinstance(by_category, dict):
            catalog.update(
                {
                    fn_id: {
                        "entrypoint": fn_obj.entrypoint
                        if hasattr(fn_obj, "entrypoint")
                        else str(fn_obj),
                        "args": {
                            name: _argument_metadata(arg)
                            for name, arg in (getattr(fn_obj, "args", {}) or {}).items()
                        },
                    }
                    for fn_id, fn_obj in by_category.items()
                }
            )
    elif isinstance(functions, dict):
        by_category = functions.get(category, {})
        if isinstance(by_category, dict):
            catalog.update(
                {
                    fn_id: {
                        "entrypoint": (
                            fn_obj.get("entrypoint")
                            if isinstance(fn_obj, dict)
                            else getattr(fn_obj, "entrypoint", str(fn_obj))
                        ),
                        "args": {
                            name: (
                                {
                                    "type": arg.get("type", "object"),
                                    "comment": arg.get("comment"),
                                }
                                if isinstance(arg, dict)
                                else _argument_metadata(arg)
                            )
                            for name, arg in (
                                fn_obj.get("args", {})
                                if isinstance(fn_obj, dict)
                                else (getattr(fn_obj, "args", {}) or {})
                            ).items()
                        },
                    }
                    for fn_id, fn_obj in by_category.items()
                }
            )

    for dataset in datasets.values():
        operations = []
        if category in {"read", "expand", "conform", "vectorize", "write"}:
            registered = (
                functions.get(category, {})
                if isinstance(functions, dict)
                else getattr(functions, category, {})
            )
            operations = [
                mapping
                for mapping in dataset.mappings.values()
                if hasattr(mapping, "binding")
                if mapping.binding.function in registered
            ]
        for operation in operations:
            if not operation.binding.function:
                continue
            function_id = operation.binding.function
            if function_id not in catalog:
                catalog[function_id] = {
                    "entrypoint": _configured_entrypoint(
                        functions, category, function_id, function_id
                    ),
                    "args": {
                        name: {**bind._argument_definition(value), "comment": None}
                        for name, value in operation.binding.args.items()
                    },
                }
    return catalog
