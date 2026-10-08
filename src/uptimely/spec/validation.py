"""Semantic validation for parsed Uptimely specifications."""

from __future__ import annotations

from typing import Any

from .json_spec.bindings import aggregation_entries


class SpecificationError(ValueError):
    """A semantic specification error with a stable code and resource path."""

    def __init__(self, message: str, *, code: str, path: tuple[str | int, ...]):
        self.code = code
        self.path = path
        location = ".".join(str(part) for part in path)
        super().__init__(f"{location}: {message}" if location else message)


def _structural_references(value: Any, prefix: str) -> list[str]:
    """Return identifiers from nested structural reference strings."""
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    if isinstance(value, str):
        return [value.removeprefix(prefix)] if value.startswith(prefix) else []
    if isinstance(value, dict):
        return [
            identifier
            for nested in value.values()
            for identifier in _structural_references(nested, prefix)
        ]
    if isinstance(value, list):
        return [
            identifier for nested in value for identifier in _structural_references(nested, prefix)
        ]
    return []


def _function_categories(model: Any) -> dict[str, dict[str, Any]]:
    """Return function implementations indexed by their catalog category."""
    catalog = model.functions
    return {
        "read": catalog.read,
        "write": catalog.write,
        "vectorize": catalog.vectorize,
        "aggregate": catalog.aggregate,
        "collapse": catalog.collapse,
        "expand": catalog.expand,
        "conform": catalog.conform,
    }


def _validate_dimensions(model: Any) -> set[str]:
    """Validate dimension parents and return declared dimension identifiers."""
    dimensions = set(model.dimensions)
    for dimension_id, dimension in model.dimensions.items():
        if dimension.parent is not None and dimension.parent not in dimensions:
            raise ValueError(
                f"Dimension {dimension_id} references unknown parent: {dimension.parent}"
            )
        lineage: list[str] = []
        current = dimension_id
        while current is not None:
            if current in lineage:
                cycle = lineage[lineage.index(current) :] + [current]
                raise SpecificationError(
                    "Dimension parent cycle: " + " -> ".join(cycle),
                    code="dimension_parent_cycle",
                    path=("dimensions", dimension_id, "parent"),
                )
            lineage.append(current)
            current_dimension = model.dimensions.get(current)
            current = current_dimension.parent if current_dimension is not None else None
    return dimensions


def validate_dataset_ids(model: Any) -> None:
    """Require dataset identifiers to be globally unambiguous."""
    owners: dict[str, str] = {}
    for entity_id, entity in model.entities.items():
        for dataset in entity.datasets:
            owner = owners.get(dataset.id)
            if owner is not None:
                raise SpecificationError(
                    f"Duplicate dataset id {dataset.id}; already declared by entity {owner}",
                    code="duplicate_dataset_id",
                    path=("entities", entity_id, "datasets", dataset.id),
                )
            owners[dataset.id] = entity_id


def _validate_entity_dimensions(model: Any, dimensions: set[str]) -> None:
    """Validate that entities refer only to declared dimensions."""
    for entity_id, entity in model.entities.items():
        unknown_dimensions = sorted(set(entity.dimensions) - dimensions)
        if unknown_dimensions:
            raise ValueError(
                f"Entity {entity_id} references unknown dimensions: "
                + ", ".join(unknown_dimensions)
            )


def _validate_calculation_bindings(entity: Any) -> None:
    """Require every declared calculation to have an executable binding."""
    for dataset in entity.datasets:
        calculations = dataset.vectorize if hasattr(dataset, "vectorize") else dataset.vectorize
        for calculation_id, calculation in calculations.items():
            if calculation.binding is None:
                raise ValueError(f"Calculation {calculation_id} must define a binding")
            references = _structural_references(calculation.binding.args, "$features.")
            if not any(reference != "@" for reference in references):
                raise ValueError(f"Vectorize {calculation_id} must reference one or more features")


def _validate_aggregations(model: Any) -> None:
    """Allow aggregations only in collapse and require source references."""
    source_features = {
        feature_id
        for entity in model.entities.values()
        for dataset in entity.datasets
        for operation_type, fragment in dataset.fragment_operations
        if operation_type != "collapse"
        for feature_id in fragment.features
    }
    for entity in model.entities.values():
        for dataset in entity.datasets:
            for operation_type, fragment in dataset.fragment_operations:
                aggregations = aggregation_entries(fragment.binding.args)
                if operation_type == "collapse" and not aggregations:
                    raise ValueError(f"Collapse {fragment.id} must define one or more aggregations")
                if operation_type != "collapse" and aggregations:
                    raise ValueError(
                        f"{operation_type} operation {fragment.id} cannot use aggregations"
                    )
                for value in aggregations:
                    function_id = value.get("function")
                    if function_id not in model.functions.aggregate:
                        raise ValueError(
                            f"Aggregation in collapse {fragment.id} references "
                            f"unknown aggregate function: {function_id}"
                        )
                    references = _structural_references(value, "$features.")
                    if not references:
                        raise ValueError(
                            f"Aggregation in collapse {fragment.id} must reference a source feature"
                        )
                    unknown = sorted(
                        reference for reference in references if reference not in source_features
                    )
                    if unknown:
                        message = (
                            f"Aggregation in collapse {fragment.id} "
                            "references non-source features: " + ", ".join(unknown)
                        )
                        raise ValueError(message)
            for calculation in (
                dataset.vectorize if hasattr(dataset, "vectorize") else dataset.vectorize
            ).values():
                if aggregation_entries(calculation.binding.args):
                    raise ValueError("Vectorize operations cannot use aggregations")
            for operation in dataset.write.values():
                if aggregation_entries(operation.binding.args):
                    raise ValueError("Write operations cannot use aggregations")


def _validate_operation_functions(entity: Any, categories: dict[str, dict[str, Any]]) -> None:
    """Validate operation references against their function catalog categories."""
    for dataset in entity.datasets:
        missing = sorted(
            fragment.binding.function
            for operation_type, fragment in dataset.fragment_operations
            if fragment.binding.function not in categories[operation_type]
        )
        if missing:
            raise ValueError(
                f"Dataset {dataset.id} fragments reference unknown functions: " + ", ".join(missing)
            )
        for operation_id, operation in dataset.write.items():
            if operation.binding.function not in categories["write"]:
                raise SpecificationError(
                    f"Write {operation_id} references unknown function: "
                    f"{operation.binding.function}",
                    code="unknown_write_function",
                    path=("datasets", dataset.id, "write", operation_id, "binding", "function"),
                )


def _validate_binding_contract(
    binding: Any,
    function: Any,
    *,
    path: tuple[str | int, ...],
) -> None:
    """Require bound argument names to match the function template contract."""
    declared = set(function.args)
    supplied = set(binding.args)
    missing = sorted(declared - supplied)
    unknown = sorted(supplied - declared)
    if missing or unknown:
        details = []
        if missing:
            details.append("missing arguments: " + ", ".join(missing))
        if unknown:
            details.append("unknown arguments: " + ", ".join(unknown))
        raise SpecificationError(
            f"Binding for function {binding.function} has " + "; ".join(details),
            code="invalid_binding_arguments",
            path=path,
        )


def _validate_binding_contracts(model: Any, categories: dict[str, dict[str, Any]]) -> None:
    """Validate argument names for every declared operation binding."""
    for entity_id, entity in model.entities.items():
        for dataset in entity.datasets:
            for operation_type, fragment in dataset.fragment_operations:
                function = categories[operation_type].get(fragment.binding.function)
                if function is not None:
                    _validate_binding_contract(
                        fragment.binding,
                        function,
                        path=(
                            "entities",
                            entity_id,
                            "datasets",
                            dataset.id,
                            operation_type,
                            fragment.id,
                            "binding",
                            "args",
                        ),
                    )
            for calculation_id, calculation in (
                dataset.vectorize if hasattr(dataset, "vectorize") else dataset.vectorize
            ).items():
                function = categories["vectorize"].get(calculation.binding.function)
                if function is not None:
                    _validate_binding_contract(
                        calculation.binding,
                        function,
                        path=(
                            "entities",
                            entity_id,
                            "datasets",
                            dataset.id,
                            "vectorize",
                            calculation_id,
                            "binding",
                            "args",
                        ),
                    )
            for operation_id, operation in dataset.write.items():
                function = categories["write"].get(operation.binding.function)
                if function is not None:
                    _validate_binding_contract(
                        operation.binding,
                        function,
                        path=(
                            "entities",
                            entity_id,
                            "datasets",
                            dataset.id,
                            "write",
                            operation_id,
                            "binding",
                            "args",
                        ),
                    )


def _validate_fragment_dimensions(entity: Any) -> None:
    """Require every fragment dataframe contract to include entity dimensions."""
    required_dimensions = set(entity.dimensions)
    for dataset in entity.datasets:
        for _, fragment in dataset.fragment_operations:
            missing_dimensions = sorted(required_dimensions - set(fragment.features))
            if missing_dimensions:
                raise ValueError(
                    f"Fragment {fragment.id} must include dimension columns: "
                    + ", ".join(missing_dimensions)
                )


def _feature_names(model: Any) -> set[str]:
    """Collect declared input and calculated feature identifiers."""
    feature_names: set[str] = set()
    for entity in model.entities.values():
        for dataset in entity.datasets:
            for _, fragment in dataset.fragment_operations:
                feature_names.update(fragment.features)
            feature_names.update(
                dataset.vectorize if hasattr(dataset, "vectorize") else dataset.vectorize
            )
    return feature_names


def _validate_feature_dependencies(
    calls: list[Any], feature_names: set[str], dimensions: set[str]
) -> None:
    """Validate that calculation dependencies resolve to features or dimensions."""
    for call in calls:
        for dependency in call.depends_on_features:
            if dependency not in feature_names and dependency not in dimensions:
                raise ValueError(
                    f"Calculation {call.feature} references unknown feature: {dependency}"
                )


def validate_specification(model: Any, calls: list[Any]) -> None:
    """Validate references and invariants after the structural model is parsed."""
    dimensions = _validate_dimensions(model)
    validate_dataset_ids(model)
    _validate_entity_dimensions(model, dimensions)
    categories = _function_categories(model)

    for entity in model.entities.values():
        _validate_calculation_bindings(entity)
        _validate_operation_functions(entity, categories)
        _validate_fragment_dimensions(entity)

    _validate_aggregations(model)
    _validate_binding_contracts(model, categories)
    _validate_feature_dependencies(calls, _feature_names(model), dimensions)
