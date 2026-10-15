"""Semantic validation for parsed analytics."""

from __future__ import annotations

import typing

from .json import bindings
from .json.json_model import functions as functions_module


class AnalyticsError(ValueError):
    """A semantic analytics error with a stable code and resource path."""

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
        operation: catalog.by_operation(operation)
        for operation in functions_module.FUNCTION_OPERATIONS
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
                raise AnalyticsError(
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
                raise AnalyticsError(
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
                    raise AnalyticsError(
                        f"Dataset {dataset.id} order references a dimension not declared "
                        f"by entity {entity_id}: {dimension}",
                        code="invalid_order_dimension",
                        path=path,
                    )
                if dimension in seen:
                    raise AnalyticsError(
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
                if model.functions[mapping.binding.function].operation != "collapse":
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
            operation = bindings.mapping_operation(mapping, model.functions)
            key = (dataset.id, mapping.id)
            dependencies[key] = set()
            for name in mapping.input_features:
                if name not in feature_names:
                    raise ValueError(
                        f"Mapping {mapping.id} references unknown input feature: {name}"
                    )
                if operation in {"vectorize", "write"} and name not in (
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
                    if operation == "collapse"
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
                        if operation == "collapse"
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


def _validate_mapping_contracts(model: typing.Any) -> None:
    """Validate feature inputs against dataframe arguments and operation dimensions."""
    datasets = {
        dataset.id: (entity_id, entity, dataset)
        for entity_id, entity in model.entities.items()
        for dataset in entity.datasets
    }
    feature_owners = {
        feature_id: (entity_id, dataset.id)
        for entity_id, entity in model.entities.items()
        for dataset in entity.datasets
        for feature_id in dataset.features
        if feature_id not in model.dimensions
    }

    for entity_id, entity in model.entities.items():
        target_dimensions = set(entity.dimension_ids)
        for dataset in entity.datasets:
            for mapping in dataset.mappings.values():
                function = model.functions[mapping.binding.function]
                operation = function.operation
                path = (
                    "entities",
                    entity_id,
                    "datasets",
                    dataset.id,
                    "mappings",
                    mapping.id,
                )
                dataframe_datasets: list[str] = []
                for argument_id, argument in function.args.items():
                    if argument.type != "dataframe":
                        continue
                    value = mapping.binding.args[argument_id]
                    if not isinstance(value, str) or not value.startswith("$datasets."):
                        raise AnalyticsError(
                            f"Dataframe argument {argument_id} must reference a dataset",
                            code="invalid_mapping_dataset_input",
                            path=(*path, "binding", "args", argument_id),
                        )
                    reference = value.removeprefix("$datasets.")
                    if reference.endswith(".id"):
                        raise AnalyticsError(
                            f"Dataframe argument {argument_id} must reference a dataframe",
                            code="invalid_mapping_dataset_input",
                            path=(*path, "binding", "args", argument_id),
                        )
                    source_id = reference.removesuffix(".dataframe")
                    source_id = dataset.id if source_id == "@" else source_id
                    if source_id not in datasets:
                        raise AnalyticsError(
                            f"Dataframe argument {argument_id} references unknown dataset "
                            f"{source_id}",
                            code="invalid_mapping_dataset_input",
                            path=(*path, "binding", "args", argument_id),
                        )
                    dataframe_datasets.append(source_id)

                if operation == "read":
                    if mapping.input_features:
                        raise AnalyticsError(
                            "Read mappings cannot declare feature inputs",
                            code="invalid_mapping_feature_inputs",
                            path=(*path, "features", "inputs"),
                        )
                    continue

                if operation in {"vectorize", "write"}:
                    if dataset.id not in dataframe_datasets:
                        raise AnalyticsError(
                            f"{operation.capitalize()} mapping must consume its target dataset",
                            code="invalid_mapping_dataset_input",
                            path=(*path, "binding", "args"),
                        )
                    invalid_inputs = sorted(
                        feature_id
                        for feature_id in mapping.input_features
                        if feature_id not in dataset.features
                        and feature_id not in target_dimensions
                    )
                    if invalid_inputs:
                        raise AnalyticsError(
                            f"{operation.capitalize()} mapping inputs must belong to its "
                            "target dataset: " + ", ".join(invalid_inputs),
                            code="invalid_mapping_feature_inputs",
                            path=(*path, "features", "inputs"),
                        )
                    continue

                if operation == "collapse":
                    source_entity, source = bindings.collapse_input_dataset(model, mapping)
                    if source.id not in dataframe_datasets:
                        raise AnalyticsError(
                            f"Collapse mapping must consume its source dataset {source.id}",
                            code="invalid_mapping_dataset_input",
                            path=(*path, "binding", "args"),
                        )
                    source_dimensions = set(source_entity.dimension_ids)
                    if source_dimensions == target_dimensions:
                        raise AnalyticsError(
                            "Collapse mapping must reduce dataset dimensionality",
                            code="invalid_mapping_dimensions",
                            path=(*path, "features", "inputs"),
                        )
                    continue

                if operation in {"conform", "expand"}:
                    unique_datasets = set(dataframe_datasets)
                    if len(unique_datasets) != 2:
                        raise AnalyticsError(
                            f"{operation.capitalize()} mapping must consume two distinct datasets",
                            code="invalid_mapping_dataset_input",
                            path=(*path, "binding", "args"),
                        )
                    input_entities = [datasets[source_id][1] for source_id in unique_datasets]
                    unavailable = sorted(
                        feature_id
                        for feature_id in mapping.input_features
                        if (
                            feature_id in model.dimensions
                            and not any(
                                feature_id in input_entity.dimension_ids
                                for input_entity in input_entities
                            )
                        )
                        or (
                            feature_id not in model.dimensions
                            and (
                                feature_id not in feature_owners
                                or feature_owners[feature_id][1] not in unique_datasets
                            )
                        )
                    )
                    if unavailable:
                        raise AnalyticsError(
                            f"{operation.capitalize()} mapping inputs must belong to its "
                            "dataframe inputs: " + ", ".join(unavailable),
                            code="invalid_mapping_feature_inputs",
                            path=(*path, "features", "inputs"),
                        )
                    input_dimensions = [
                        set(datasets[source_id][1].dimension_ids) for source_id in unique_datasets
                    ]
                    if operation == "conform" and any(
                        dimensions != target_dimensions for dimensions in input_dimensions
                    ):
                        raise AnalyticsError(
                            "Conform mapping inputs must preserve target dimensionality",
                            code="invalid_mapping_dimensions",
                            path=(*path, "binding", "args"),
                        )
                    if operation == "conform" and (
                        dataset.id not in unique_datasets
                        or any(datasets[source_id][0] != entity_id for source_id in unique_datasets)
                    ):
                        raise AnalyticsError(
                            "Conform mapping must combine its target dataset with a dataset "
                            "from the same entity",
                            code="invalid_mapping_entity",
                            path=(*path, "binding", "args"),
                        )
                    if operation == "expand":
                        target_is_input = dataset.id in unique_datasets
                        lower_dataset_ids = {
                            source_id
                            for source_id in unique_datasets
                            if set(datasets[source_id][1].dimension_ids) < target_dimensions
                        }
                        lower_dimensional_input = bool(lower_dataset_ids)
                        lower_dimensional_features = any(
                            feature_owners.get(feature_id, ("", ""))[1] in lower_dataset_ids
                            for feature_id in mapping.input_features
                        )
                        if (
                            not target_is_input
                            or not lower_dimensional_input
                            or not lower_dimensional_features
                        ):
                            raise AnalyticsError(
                                "Expand mapping must combine its target dataset with a "
                                "declared feature from a lower-dimensional dataset",
                                code="invalid_mapping_dimensions",
                                path=(*path, "binding", "args"),
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
        raise AnalyticsError(
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
                raise AnalyticsError(
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


def _validate_function_contracts(model: typing.Any) -> None:
    """Validate function return and dataframe-input contracts for each operation."""
    dataframe_inputs = {
        "read": 0,
        "collapse": 1,
        "conform": 2,
        "expand": 2,
        "vectorize": 1,
        "write": 1,
    }
    for function_id, function in model.functions.root.items():
        expected_returns = "none" if function.operation == "write" else "dataframe"
        path = ("functions", function_id)
        if function.returns != expected_returns:
            raise AnalyticsError(
                f"Operation {function.operation} must declare returns={expected_returns}",
                code="invalid_function_return_contract",
                path=(*path, "returns"),
            )
        actual_inputs = sum(argument.type == "dataframe" for argument in function.args.values())
        expected_inputs = dataframe_inputs[function.operation]
        if actual_inputs != expected_inputs:
            raise AnalyticsError(
                f"Operation {function.operation} requires {expected_inputs} dataframe "
                f"argument(s), got {actual_inputs}",
                code="invalid_function_input_contract",
                path=(*path, "args"),
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


def validate_analytics(model: typing.Any, calls: list[typing.Any]) -> None:
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
    _validate_function_contracts(model)
    _validate_mapping_contracts(model)
    _validate_feature_dependencies(calls, _feature_names(model), dimensions)
