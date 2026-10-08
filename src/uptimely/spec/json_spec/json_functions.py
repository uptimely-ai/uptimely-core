from typing import Any

from pydantic import BaseModel

from ..python_spec.bind import _argument_definition
from .json_model import Dimension


def _argument_metadata(argument: Any) -> dict[str, Any]:
    """Serialize an argument definition."""
    return {"type": argument.type, "comment": argument.comment}


def python_to_spec_dict(
    datasets: object | None = None,
    functions: Any = None,
    name: str | None = None,
    dimensions: dict[str, Dimension] | list[Dimension] | None = None,
    *,
    entities: object | None = None,
) -> dict[str, Any]:
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

    if not all(isinstance(dataset, BaseModel) for dataset in dataset_values.values()):
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


def _resources_by_id(resources: dict[str, Any] | list[Any] | None) -> dict[str, Any]:
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


def _configured_entrypoint(functions: Any, category: str, function_name: str, fallback: str) -> str:
    """Return the configured entrypoint or the declared fallback."""
    if isinstance(functions, BaseModel):
        lookup = getattr(functions, category, {})
    elif isinstance(functions, dict):
        lookup = functions.get(category, {})
    else:
        lookup = {}

    if isinstance(lookup, dict):
        configured = lookup.get(function_name)
        if isinstance(configured, BaseModel):
            return str(configured.entrypoint)
        if isinstance(configured, dict):
            entrypoint = configured.get("entrypoint")
            if entrypoint:
                return str(entrypoint)
    return fallback


def _configured_function(functions: Any, category: str, function_name: str) -> Any:
    """Return a configured function model or mapping entry, when available."""
    if isinstance(functions, BaseModel):
        lookup = getattr(functions, category, {})
        return lookup.get(function_name) if isinstance(lookup, dict) else None
    if isinstance(functions, dict):
        lookup = functions.get(category, {})
        return lookup.get(function_name) if isinstance(lookup, dict) else None
    return None


def _auto_function_catalog(declarations: object) -> dict[str, Any]:
    """Build an automatic function catalog from original Python declarations."""
    from uptimely.spec.python_spec.bind import _entrypoint
    from uptimely.spec.python_spec.feature import Aggregation

    merged: dict[str, dict[str, Any]] = {
        "read": {},
        "write": {},
        "vectorize": {},
        "aggregate": {},
        "collapse": {},
        "expand": {},
        "conform": {},
    }

    declaration_list = (
        list(declarations.values()) if isinstance(declarations, dict) else list(declarations or [])
    )

    def register_bind(function_id: str, bind: Any, category: str) -> None:
        if bind is None or getattr(bind, "function", None) is None:
            return
        function = bind.function
        entrypoint = _entrypoint(function) if callable(function) else function_id
        merged[category][function_id] = {
            "entrypoint": entrypoint,
            "args": {
                name: {**_argument_definition(value), "comment": None}
                for name, value in getattr(bind, "args", {}).items()
            },
        }

    def register_aggregations(value: Any) -> None:
        if isinstance(value, Aggregation):
            register_bind(value.id, value, "aggregate")
            return
        if isinstance(value, (list, tuple)):
            for item in value:
                register_aggregations(item)
        elif isinstance(value, dict):
            for item in value.values():
                register_aggregations(item)

    def register_dataset(dataset: Any) -> None:
        for category in ("read", "conform", "expand", "collapse"):
            for operation in getattr(dataset, category, []) or []:
                function_id = operation.bind.function_id or operation.bind.function.__name__
                register_bind(function_id, operation.bind, category)
                if category == "collapse":
                    register_aggregations(operation.bind.args)
        for sink in getattr(dataset, "write", []) or []:
            function_id = sink.bind.function_id or sink.bind.function.__name__
            register_bind(function_id, sink.bind, "write")
        for calculation in (
            getattr(dataset, "vectorize", getattr(dataset, "vectorize", []) or []) or []
        ):
            if calculation.bind is None:
                continue
            function_id = calculation.bind.function_id or calculation.bind.function.__name__
            register_bind(function_id, calculation.bind, "vectorize")

    for declaration in declaration_list:
        if hasattr(declaration, "datasets"):
            for dataset in getattr(declaration, "datasets", []) or []:
                register_dataset(dataset)
        elif hasattr(declaration, "read") and (
            hasattr(declaration, "vectorize") or hasattr(declaration, "vectorize")
        ):
            register_dataset(declaration)

    return merged


def _static_datasets_to_spec(
    datasets: dict[str, BaseModel],
    name: str | None,
    functions: dict[str, Any],
    dimensions: dict[str, Dimension],
    entities: dict[str, BaseModel] | None = None,
) -> dict[str, Any]:
    """Convert specification-layer dataset models into a specification."""
    entity_id = name or "entity"
    vectorize: dict[str, Any] = {}
    dataset_entries: list[dict[str, Any]] = []

    for dataset in datasets.values():
        entry = dataset.model_dump(exclude_none=False)
        entry["id"] = dataset.id
        for calculation in (
            dataset.vectorize if hasattr(dataset, "vectorize") else dataset.vectorize
        ).values():
            if calculation.binding is None:
                continue
            arguments = {
                name: {
                    "type": value.type if isinstance(value, BaseModel) else "object",
                    "comment": None,
                }
                for name, value in calculation.binding.args.items()
            }
            configured_function = _configured_function(
                functions, "vectorize", calculation.binding.function
            )
            if isinstance(configured_function, BaseModel) and configured_function.args:
                arguments = {
                    name: _argument_metadata(value)
                    for name, value in configured_function.args.items()
                }
            elif isinstance(configured_function, dict) and configured_function.get("args"):
                arguments = configured_function["args"]
            vectorize[calculation.binding.function] = {
                "entrypoint": _configured_entrypoint(
                    functions,
                    "vectorize",
                    calculation.binding.function,
                    calculation.binding.function,
                ),
                "description": calculation.description,
                "args": arguments,
            }
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
        "version": "0.1.0",
        "dimensions": {
            identifier: resource.model_dump(exclude_none=False)
            for identifier, resource in dimensions.items()
        },
        "functions": {
            "read": _static_function_catalog(datasets, functions, "read"),
            "write": _static_function_catalog(datasets, functions, "write"),
            "vectorize": {
                **_static_function_catalog(datasets, functions, "vectorize"),
                **vectorize,
            },
            "aggregate": _static_function_catalog(datasets, functions, "aggregate"),
            "collapse": _static_function_catalog(datasets, functions, "collapse"),
            "expand": _static_function_catalog(datasets, functions, "expand"),
            "conform": _static_function_catalog(datasets, functions, "conform"),
        },
        "entities": entity_values,
    }


def _static_function_catalog(
    datasets: dict[str, BaseModel], functions: dict[str, Any], category: str
) -> dict[str, Any]:
    """Build the function catalog for a given operation category."""
    catalog: dict[str, Any] = {}
    if isinstance(functions, BaseModel):
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
        if category in {"read", "collapse", "expand", "conform"}:
            operations.extend(getattr(dataset, category).values())
        elif category == "write":
            operations.extend(dataset.write.values())
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
                        name: {**_argument_definition(value), "comment": None}
                        for name, value in operation.binding.args.items()
                    },
                }
    return catalog
