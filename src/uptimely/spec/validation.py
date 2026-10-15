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
        return (
            [value.removeprefix(prefix).removesuffix(".id").removesuffix(".dataframe")]
            if value.startswith(prefix)
            else []
        )
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
        unknown_dimensions = sorted(set(entity.dimension_ids) - dimensions)
        if unknown_dimensions:
            raise ValueError(
                f"Entity {entity_id} references unknown dimensions: "
                + ", ".join(unknown_dimensions)
            )


def _validate_calculation_bindings(
    entity: typing.Any, categories: dict[str, dict[str, typing.Any]]
) -> None:
    """Require mappings to reference registered features and unique outputs."""
    dimensions = set(entity.dimension_ids)
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
                if mapping.output_features:
                    raise ValueError(f"Write mapping {mapping_id} cannot produce features")
                continue
            if not mapping.output_features:
                raise ValueError(f"Mapping {mapping_id} must declare one or more features")
            if matches[0] == "vectorize":
                collisions = sorted(set(mapping.output_features) & dimensions)
                if collisions:
                    raise ValueError(
                        "Calculated feature names cannot duplicate entity dimensions: "
                        + ", ".join(collisions)
                    )
            for feature_id in mapping.output_features:
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
                if len(mapping.output_features) > 1 and "@" in _structural_references(
                    mapping.binding.args, "$features."
                ):
                    raise ValueError(
                        f"Vectorize mapping {mapping_id} cannot use $features.@ "
                        "when it produces multiple features"
                    )
            elif matches[0] == "collapse":
                outputs = set(mapping.output_features) - dimensions
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
        missing = sorted(set(dataset.features) - set(owners) - dimensions)
        if missing:
            raise ValueError("Features have no producer mapping: " + ", ".join(missing))


def _validate_dataset_order(model: typing.Any) -> None:
    """Require distinct ordering keys belonging to the dataset's entity."""
    for entity_id, entity in model.entities.items():
        dimensions = set(entity.dimension_ids)
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
    """Validate inferred input datasets, target keys, and explicit inputs."""
    for entity in model.entities.values():
        for dataset in entity.datasets:
            for mapping in dataset.mappings.values():
                if mapping.binding.function not in model.functions.collapse:
                    continue
                binding = mapping.binding
                source_entity, source = bindings.collapse_input_dataset(model, mapping)
                source_id = source.id
                if source_id == dataset.id:
                    raise ValueError(
                        f"Collapse {mapping.id} cannot use its target dataset as source"
                    )
                keys = entity.dimension_ids
                if not set(keys).issubset(source_entity.dimension_ids):
                    raise ValueError(
                        f"Collapse {mapping.id} grouping dimensions must exist "
                        f"in source {source_id}"
                    )
                source_features = set(source.features) | set(source_entity.dimension_ids)
                inputs = mapping.input_features
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
                ) - set(source_entity.dimension_ids)
                if unknown_dimensions:
                    raise ValueError(
                        f"Collapse {mapping.id} references unknown source dimensions: "
                        + ", ".join(sorted(unknown_dimensions))
                    )


def _validate_mapping_inputs(model: typing.Any) -> None:
    """Validate explicit dataflow, argument references, and observation requirements."""
    datasets = {
        dataset.id: (entity, dataset)
        for entity in model.entities.values()
        for dataset in entity.datasets
    }
    feature_names = _feature_names(model) | set(model.dimensions)
    producers = {
        output: (dataset.id, mapping.id)
        for _, dataset in datasets.values()
        for mapping in dataset.mappings.values()
        for output in mapping.output_features
        if output not in model.dimensions
    }
    dependencies: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for entity, dataset in datasets.values():
        for mapping in dataset.mappings.values():
            category = bindings.mapping_category(mapping, model.functions)
            key = (dataset.id, mapping.id)
            dependencies[key] = set()
            for name in mapping.input_features:
                if name not in feature_names:
                    raise ValueError(
                        f"Mapping {mapping.id} references unknown input feature: {name}"
                    )
                if category in {"vectorize", "write"} and name not in (
                    set(dataset.features) | set(entity.dimension_ids)
                ):
                    raise ValueError(
                        f"Mapping {mapping.id} cannot read feature {name} from another dataset"
                    )
                if name in producers:
                    dependencies[key].add(producers[name])
            for name in _structural_references(mapping.binding.args, "$features."):
                if name != "@" and name not in feature_names:
                    raise ValueError(f"Mapping {mapping.id} references unknown feature: {name}")
            for name in _structural_references(mapping.binding.args, "$datasets."):
                if name != "@" and name not in datasets:
                    raise ValueError(f"Mapping {mapping.id} references unknown dataset: {name}")
            for name in _structural_references(mapping.binding.args, "$dimensions."):
                if name not in model.dimensions:
                    raise ValueError(f"Mapping {mapping.id} references unknown dimension: {name}")
            if mapping.row_context is not None:
                context_dataset = (
                    bindings.collapse_input_dataset(model, mapping)[1]
                    if category == "collapse"
                    else dataset
                )
                if mapping.row_context.requires_order and not context_dataset.order:
                    raise ValueError(
                        f"Mapping {mapping.id} directional row context requires dataset order"
                    )
                dimension = mapping.row_context.dimension
                if dimension is not None:
                    identifier = dimension.removeprefix("$dimensions.")
                    context_entity = (
                        bindings.collapse_input_dataset(model, mapping)[0]
                        if category == "collapse"
                        else entity
                    )
                    if identifier not in context_entity.dimension_ids:
                        raise ValueError(
                            f"Mapping {mapping.id} context dimension is not in the input entity: "
                            f"{identifier}"
                        )
                    measures = {
                        measure
                        for direction in (mapping.row_context.before, mapping.row_context.after)
                        if hasattr(direction, "model_dump")
                        for measure in direction.model_dump(exclude_none=True)
                    }
                    expected = "datetime" if "time" in measures else "integer"
                    if measures and model.dimensions[identifier].type != expected:
                        raise ValueError(
                            f"Mapping {mapping.id} context dimension must have type {expected}"
                        )
                    if mapping.row_context.requires_order and dimension not in {
                        key.dimension for key in context_dataset.order
                    }:
                        raise ValueError(
                            f"Mapping {mapping.id} context dimension must occur in dataset order"
                        )
    visiting: set[tuple[str, str]] = set()
    visited: set[tuple[str, str]] = set()

    def visit(key: tuple[str, str]) -> None:
        if key in visiting:
            raise ValueError(f"Mapping feature dependency cycle: {key[0]}.{key[1]}")
        if key in visited:
            return
        visiting.add(key)
        for dependency in dependencies[key]:
            visit(dependency)
        visiting.remove(key)
        visited.add(key)

    for key in dependencies:
        visit(key)


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

    def validate_selector(value: object, argument_type: str) -> None:
        if isinstance(value, str) and value.startswith("$"):
            if value.startswith("$datasets.") and value.endswith(".dataframe"):
                expected = "dataframe"
            elif value.endswith(".id"):
                expected = "string"
            else:
                return
            if argument_type != expected:
                raise SpecificationError(
                    f"Reference {value} requires argument type {expected}, got {argument_type}",
                    code="invalid_binding_reference_type",
                    path=path,
                )
        elif isinstance(value, list):
            element_type = argument_type[6:-1] if argument_type.startswith("array[") else "string"
            for item in value:
                validate_selector(item, element_type)
        elif isinstance(value, dict):
            value_type = (
                argument_type[12:-1] if argument_type.startswith("object{str: ") else "string"
            )
            for item in value.values():
                validate_selector(item, value_type)

    for name, value in binding.args.items():
        validate_selector(value, function.args[name].type)


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
    _validate_mapping_inputs(model)
    _validate_binding_contracts(model, categories)
    _validate_feature_dependencies(calls, _feature_names(model), dimensions)
