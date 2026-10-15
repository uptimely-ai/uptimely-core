from __future__ import annotations

import typing

import pydantic

from . import json_model


def _argument_metadata(argument: typing.Any) -> dict[str, typing.Any]:
    """Serialize an argument definition."""
    return {"type": argument.type, "comment": argument.comment}


def _function_metadata(function: json_model.FunctionTemplate) -> dict[str, typing.Any]:
    """Serialize a function definition without unset optional metadata."""
    metadata = function.model_dump(exclude={"id"})
    if metadata.get("description") is None:
        metadata.pop("description")
    return metadata


def python_to_analytics_dict(
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

    return _static_datasets_to_analytics(
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


def _auto_function_catalog(declarations: object) -> dict[str, typing.Any]:
    """Build an automatic function catalog from original Python declarations."""
    merged: dict[str, typing.Any] = {}

    declaration_list = (
        list(declarations.values()) if isinstance(declarations, dict) else list(declarations or [])
    )

    def register_dataset(dataset: typing.Any) -> None:
        for function_id, function in dataset.function_catalog().root.items():
            existing = merged.get(function_id)
            serialized = _function_metadata(function)
            if existing is not None and existing != serialized:
                raise ValueError(f"Conflicting function definition for '{function_id}'")
            merged[function_id] = serialized

    for declaration in declaration_list:
        if hasattr(declaration, "datasets"):
            for dataset in getattr(declaration, "datasets", []) or []:
                register_dataset(dataset)
        elif hasattr(declaration, "mappings"):
            register_dataset(declaration)

    return merged


def _static_datasets_to_analytics(
    datasets: dict[str, pydantic.BaseModel],
    name: str | None,
    functions: dict[str, typing.Any],
    dimensions: dict[str, json_model.Dimension],
    entities: dict[str, pydantic.BaseModel] | None = None,
) -> dict[str, typing.Any]:
    """Convert Python dataset models into an analytics document."""
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

    function_definitions: dict[str, typing.Any] = {}
    if isinstance(functions, json_model.FunctionCatalog):
        function_definitions.update(
            {
                function_id: _function_metadata(definition)
                for function_id, definition in functions.root.items()
            }
        )
    elif isinstance(functions, dict):
        for function_id, definition in functions.items():
            if isinstance(definition, pydantic.BaseModel):
                function_definitions[function_id] = _function_metadata(definition)
            else:
                metadata = dict(definition)
                if metadata.get("description") is None:
                    metadata.pop("description", None)
                function_definitions[function_id] = metadata

    for dataset in datasets.values():
        if hasattr(dataset, "function_catalog"):
            for function_id, definition in dataset.function_catalog().root.items():
                function_definitions.setdefault(function_id, _function_metadata(definition))

    return {
        **({"name": name} if name is not None else {}),
        "version": "0.2.0",
        "source": {"name": "python_api", "generated": True},
        "dimensions": {
            identifier: resource.model_dump(exclude_none=False)
            for identifier, resource in dimensions.items()
        },
        "functions": function_definitions,
        "entities": entity_values,
    }
