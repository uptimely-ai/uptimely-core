"""Semantic validation for parsed Uptimely specifications."""

from __future__ import annotations

import typing

from .json_spec import bindings


class SpecificationError(ValueError):
    """A semantic specification error with a stable code and resource path."""

    def __init__(self, message: str, *, code: str, path: tuple[str | int, ...]):
        self.code = code
        self.path = path
        location = ".".join(str(part) for part in path)
        super().__init__(f"{location}: {message}" if location else message)


def _structural_references(value: typing.Any, prefix: str) -> list[str]:
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


def _function_categories(model: typing.Any) -> dict[str, dict[str, typing.Any]]:
    """Return function implementations indexed by their catalog category."""
    catalog = model.functions
    return {
        "read": catalog.read,
        "write": catalog.write,
        "vectorize": catalog.vectorize,
        "collapse": catalog.collapse,
        "expand": catalog.expand,
        "conform": catalog.conform,
    }


def _validate_dimensions(model: typing.Any) -> set[str]:
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


def validate_dataset_ids(model: typing.Any) -> None:
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


def _validate_entity_dimensions(model: typing.Any, dimensions: set[str]) -> None:
    """Validate that entities refer only to declared dimensions."""
    for entity_id, entity in model.entities.items():
        unknown_dimensions = sorted(set(entity.dimensions) - dimensions)
        if unknown_dimensions:
            raise ValueError(
                f"Entity {entity_id} references unknown dimensions: "
                + ", ".join(unknown_dimensions)
            )


def _validate_calculation_bindings(
    entity: typing.Any, categories: dict[str, dict[str, typing.Any]]
) -> None:
    """Require mappings to reference registered features and unique outputs."""
    dimensions = set(entity.dimensions)
    for dataset in entity.datasets:
        owners: dict[str, str] = {}
        for mapping_id, mapping in dataset.mappings.items():
            matches = [
                category
                for category in ("read", "conform", "expand", "collapse", "vectorize", "write")
                if mapping.binding.function in categories[category]
            ]
            if not matches:
                raise ValueError(
                    f"Dataset {dataset.id} mappings reference unknown functions: "
                    f"{mapping.binding.function}"
                )
            if len(matches) != 1:
                raise ValueError(
                    f"Mapping {mapping_id} function {mapping.binding.function} must resolve "
                    "to exactly one operation category"
                )
            if matches[0] == "write":
                if mapping.features:
                    raise ValueError(f"Write mapping {mapping_id} cannot produce features")
                continue
            if not mapping.features:
                raise ValueError(f"Mapping {mapping_id} must declare one or more features")
            if matches[0] == "vectorize":
                collisions = sorted(set(mapping.features) & dimensions)
                if collisions:
                    raise ValueError(
                        "Calculated feature names cannot duplicate entity dimensions: "
                        + ", ".join(collisions)
                    )
            for feature_id in mapping.features:
                if feature_id not in dataset.features:
                    raise ValueError(
                        f"Mapping {mapping_id} references unknown feature: {feature_id}"
                    )
                if feature_id in dimensions:
                    continue
                if feature_id in owners:
                    raise ValueError(
                        f"Feature {feature_id} is produced by multiple mappings: "
                        f"{owners[feature_id]}, {mapping_id}"
                    )
                owners[feature_id] = mapping_id
            if matches[0] == "vectorize":
                if len(mapping.features) > 1 and "@" in _structural_references(
                    mapping.binding.args, "$features."
                ):
                    raise ValueError(
                        f"Vectorize mapping {mapping_id} cannot use $features.@ "
                        "when it produces multiple features"
                    )
                references = _structural_references(mapping.binding.args, "$features.")
                if not references:
                    raise ValueError(f"Vectorize mapping {mapping_id} must reference features")
            elif matches[0] == "collapse":
                outputs = set(mapping.features) - dimensions
                if not outputs:
                    raise ValueError(
                        f"Collapse mapping {mapping_id} must produce a non-dimension feature"
                    )
                if len(outputs) > 1 and "@" in _structural_references(
                    mapping.binding.args, "$features."
                ):
                    raise ValueError(
                        f"Collapse mapping {mapping_id} cannot use $features.@ "
                        "when it produces multiple features"
                    )
            if matches[0] in {"read", "conform", "expand", "collapse"}:
                missing_dimensions = sorted(dimensions - set(mapping.features))
                if missing_dimensions:
                    raise ValueError(
                        f"Mapping {mapping_id} must include dimension columns: "
                        + ", ".join(missing_dimensions)
                    )
        missing = sorted(set(dataset.features) - set(owners) - dimensions)
        if missing:
            raise ValueError("Features have no producer mapping: " + ", ".join(missing))


def _validate_dataset_order(model: typing.Any) -> None:
    """Require distinct ordering keys belonging to the dataset's entity."""
    for entity_id, entity in model.entities.items():
        dimensions = set(entity.dimensions)
        for dataset in entity.datasets:
            seen: set[str] = set()
            for index, key in enumerate(dataset.order):
                dimension = key.dimension.removeprefix("$dimensions.")
                path = ("entities", entity_id, "datasets", dataset.id, "order", index, "dimension")
                if dimension not in dimensions:
                    raise SpecificationError(
                        f"Dataset {dataset.id} order references a dimension not declared "
                        f"by entity {entity_id}: {dimension}",
                        code="invalid_order_dimension",
                        path=path,
                    )
                if dimension in seen:
                    raise SpecificationError(
                        f"Dataset {dataset.id} order repeats dimension: {dimension}",
                        code="duplicate_order_dimension",
                        path=path,
                    )
                seen.add(dimension)


def _validate_collapses(model: typing.Any) -> None:
    """Validate inferred input datasets, grouping keys, and reducer inputs."""
    for entity in model.entities.values():
        for dataset in entity.datasets:
            for mapping in dataset.mappings.values():
                if mapping.binding.function not in model.functions.collapse:
                    continue
                binding = mapping.binding
                if _structural_references(binding.args, "$datasets."):
                    raise ValueError(
                        f"Collapse function {binding.function} cannot bind a dataset; "
                        "bind its input features or dimensions instead"
                    )
                source_entity, source = bindings.collapse_input_dataset(model, mapping)
                source_id = source.id
                if source_id == dataset.id:
                    raise ValueError(
                        f"Collapse {mapping.id} cannot use its target dataset as source"
                    )
                keys = entity.dimensions
                if not set(keys).issubset(source_entity.dimensions):
                    raise ValueError(
                        f"Collapse {mapping.id} grouping dimensions must exist "
                        f"in source {source_id}"
                    )
                source_features = set(source.features) | set(source_entity.dimensions)
                references = _structural_references(binding.args, "$features.")
                inputs = [reference for reference in references if reference != "@"]
                if not inputs:
                    raise ValueError(f"Collapse {mapping.id} must reference a source feature")
                unknown = sorted(set(inputs) - source_features)
                if unknown:
                    raise ValueError(
                        f"Collapse {mapping.id} references features outside source {source_id}: "
                        + ", ".join(unknown)
                    )
                unknown_dimensions = set(
                    _structural_references(binding.args, "$dimensions.")
                ) - set(source_entity.dimensions)
                if unknown_dimensions:
                    raise ValueError(
                        f"Collapse {mapping.id} references unknown source dimensions: "
                        + ", ".join(sorted(unknown_dimensions))
                    )


def _validate_operation_functions(
    entity: typing.Any, categories: dict[str, dict[str, typing.Any]]
) -> None:
    """Validate operation references against their function catalog categories."""
    for dataset in entity.datasets:
        missing = sorted(
            mapping.binding.function
            for mapping in dataset.mappings.values()
            if not any(
                mapping.binding.function in categories[category]
                for category in ("read", "conform", "expand", "collapse", "vectorize", "write")
            )
        )
        if missing:
            raise ValueError(
                f"Dataset {dataset.id} mappings reference unknown functions: " + ", ".join(missing)
            )


def _validate_binding_contract(
    binding: typing.Any,
    function: typing.Any,
    *,
    path: tuple[str | int, ...],
    additional_arguments: set[str] | None = None,
) -> None:
    """Require bound argument names to match the function template contract."""
    declared = set(function.args)
    supplied = set(binding.args) | (additional_arguments or set())
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


def _validate_binding_contracts(
    model: typing.Any, categories: dict[str, dict[str, typing.Any]]
) -> None:
    """Validate argument names for every declared operation binding."""
    for entity_id, entity in model.entities.items():
        for dataset in entity.datasets:
            for mapping_id, mapping in dataset.mappings.items():
                function = next(
                    (
                        functions[mapping.binding.function]
                        for category, functions in categories.items()
                        if mapping.binding.function in functions
                    ),
                    None,
                )
                if function is not None:
                    _validate_binding_contract(
                        mapping.binding,
                        function,
                        path=(
                            "entities",
                            entity_id,
                            "datasets",
                            dataset.id,
                            "mappings",
                            mapping_id,
                            "binding",
                            "args",
                        ),
                    )


def _feature_names(model: typing.Any) -> set[str]:
    """Collect declared feature identifiers."""
    return {
        feature_id
        for entity in model.entities.values()
        for dataset in entity.datasets
        for feature_id in dataset.features
    }


def _validate_feature_dependencies(
    calls: list[typing.Any], feature_names: set[str], dimensions: set[str]
) -> None:
    """Validate that calculation dependencies resolve to features or dimensions."""
    for call in calls:
        for dependency in call.depends_on_features:
            if dependency not in feature_names and dependency not in dimensions:
                raise ValueError(
                    f"Calculation {call.feature} references unknown feature: {dependency}"
                )


def validate_specification(model: typing.Any, calls: list[typing.Any]) -> None:
    """Validate references and invariants after the structural model is parsed."""
    dimensions = _validate_dimensions(model)
    validate_dataset_ids(model)
    _validate_entity_dimensions(model, dimensions)
    _validate_dataset_order(model)
    categories = _function_categories(model)

    for entity in model.entities.values():
        _validate_calculation_bindings(entity, categories)
        _validate_operation_functions(entity, categories)

    _validate_collapses(model)
    _validate_binding_contracts(model, categories)
    _validate_feature_dependencies(calls, _feature_names(model), dimensions)
