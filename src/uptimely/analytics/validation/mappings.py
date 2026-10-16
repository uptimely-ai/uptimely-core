"""Mapping, binding, and dataflow validation rules."""

from __future__ import annotations

import typing

from uptimely import contracts

from .. import references as bindings
from . import context as context_module
from . import errors

__all__ = [
    "_validate_calculation_bindings",
    "_validate_collapses",
    "_validate_mapping_contracts",
    "_validate_mapping_inputs",
]


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
                for category in contracts.FUNCTION_OPERATIONS
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
                if len(
                    mapping.output_features
                ) > 1 and contracts.CURRENT_ID in context_module._structural_references(
                    mapping.binding.args, contracts.FEATURE_PREFIX
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
                if len(
                    outputs
                ) > 1 and contracts.CURRENT_ID in context_module._structural_references(
                    mapping.binding.args, contracts.FEATURE_PREFIX
                ):
                    raise ValueError(
                        f"Collapse mapping {mapping_id} cannot use $features.@ "
                        "when it produces multiple features"
                    )
        missing = sorted(set(dataset.features) - set(owners) - dimensions)
        if missing:
            raise ValueError("Features have no producer mapping: " + ", ".join(missing))


def _validate_collapses(validation_context: context_module.AnalyticsValidationContext) -> None:
    """Validate inferred input datasets, target keys, and explicit inputs."""
    model = validation_context.model
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
                    context_module._structural_references(binding.args, contracts.DIMENSION_PREFIX)
                ) - set(source_entity.dimension_ids)
                if unknown_dimensions:
                    raise ValueError(
                        f"Collapse {mapping.id} references unknown source dimensions: "
                        + ", ".join(sorted(unknown_dimensions))
                    )


def _validate_mapping_inputs(
    validation_context: context_module.AnalyticsValidationContext,
) -> None:
    """Validate explicit dataflow, argument references, and observation requirements."""
    model = validation_context.model
    feature_names = validation_context.feature_names | validation_context.dimension_ids
    dependencies: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for dataset_id in validation_context.datasets_by_id:
        location = validation_context.dataset(dataset_id)
        if location is None:
            continue
        entity, dataset = location.entity, location.dataset
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
                producer = validation_context.last_feature_producer(name)
                if producer is not None:
                    dependencies[key].add((producer.dataset_id, producer.mapping_id))
            for name in context_module._structural_references(
                mapping.binding.args, contracts.FEATURE_PREFIX
            ):
                if name != contracts.CURRENT_ID and name not in feature_names:
                    raise ValueError(f"Mapping {mapping.id} references unknown feature: {name}")
            for name in context_module._structural_references(
                mapping.binding.args, contracts.DATASET_PREFIX
            ):
                if name != contracts.CURRENT_ID and name not in validation_context.datasets_by_id:
                    raise ValueError(f"Mapping {mapping.id} references unknown dataset: {name}")
            for name in context_module._structural_references(
                mapping.binding.args, contracts.DIMENSION_PREFIX
            ):
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
                    identifier = dimension.removeprefix(contracts.DIMENSION_PREFIX)
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


def _validate_mapping_contracts(
    validation_context: context_module.AnalyticsValidationContext,
) -> None:
    """Validate feature inputs against dataframe arguments and operation dimensions."""
    model = validation_context.model

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
                    if not isinstance(value, str) or not value.startswith(contracts.DATASET_PREFIX):
                        raise errors.AnalyticsError(
                            f"Dataframe argument {argument_id} must reference a dataset",
                            code="invalid_mapping_dataset_input",
                            path=(*path, "binding", "args", argument_id),
                        )
                    reference = value.removeprefix(contracts.DATASET_PREFIX)
                    if reference.endswith(contracts.ID_SELECTOR):
                        raise errors.AnalyticsError(
                            f"Dataframe argument {argument_id} must reference a dataframe",
                            code="invalid_mapping_dataset_input",
                            path=(*path, "binding", "args", argument_id),
                        )
                    source_id = reference.removesuffix(contracts.DATAFRAME_SELECTOR)
                    source_id = dataset.id if source_id == contracts.CURRENT_ID else source_id
                    source_location = validation_context.dataset(source_id)
                    if source_location is None:
                        raise errors.AnalyticsError(
                            f"Dataframe argument {argument_id} references unknown dataset "
                            f"{source_id}",
                            code="invalid_mapping_dataset_input",
                            path=(*path, "binding", "args", argument_id),
                        )
                    dataframe_datasets.append(source_id)

                if operation == "read":
                    if mapping.input_features:
                        raise errors.AnalyticsError(
                            "Read mappings cannot declare feature inputs",
                            code="invalid_mapping_feature_inputs",
                            path=(*path, "features", "inputs"),
                        )
                    continue

                if operation in {"vectorize", "write"}:
                    if dataset.id not in dataframe_datasets:
                        raise errors.AnalyticsError(
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
                        raise errors.AnalyticsError(
                            f"{operation.capitalize()} mapping inputs must belong to its "
                            "target dataset: " + ", ".join(invalid_inputs),
                            code="invalid_mapping_feature_inputs",
                            path=(*path, "features", "inputs"),
                        )
                    continue

                if operation == "collapse":
                    source_entity, source = bindings.collapse_input_dataset(model, mapping)
                    if source.id not in dataframe_datasets:
                        raise errors.AnalyticsError(
                            f"Collapse mapping must consume its source dataset {source.id}",
                            code="invalid_mapping_dataset_input",
                            path=(*path, "binding", "args"),
                        )
                    source_dimensions = set(source_entity.dimension_ids)
                    if source_dimensions == target_dimensions:
                        raise errors.AnalyticsError(
                            "Collapse mapping must reduce dataset dimensionality",
                            code="invalid_mapping_dimensions",
                            path=(*path, "features", "inputs"),
                        )
                    continue

                if operation in {"conform", "expand"}:
                    unique_datasets = set(dataframe_datasets)
                    if len(unique_datasets) != 2:
                        raise errors.AnalyticsError(
                            f"{operation.capitalize()} mapping must consume two distinct datasets",
                            code="invalid_mapping_dataset_input",
                            path=(*path, "binding", "args"),
                        )
                    input_locations = [
                        validation_context.dataset(source_id) for source_id in unique_datasets
                    ]
                    input_entities = [
                        location.entity for location in input_locations if location is not None
                    ]
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
                                (owner := validation_context.last_feature_owner(feature_id)) is None
                                or owner.dataset.id not in unique_datasets
                            )
                        )
                    )
                    if unavailable:
                        raise errors.AnalyticsError(
                            f"{operation.capitalize()} mapping inputs must belong to its "
                            "dataframe inputs: " + ", ".join(unavailable),
                            code="invalid_mapping_feature_inputs",
                            path=(*path, "features", "inputs"),
                        )
                    input_dimensions = [
                        set(location.entity.dimension_ids)
                        for location in input_locations
                        if location is not None
                    ]
                    if operation == "conform" and any(
                        dimensions != target_dimensions for dimensions in input_dimensions
                    ):
                        raise errors.AnalyticsError(
                            "Conform mapping inputs must preserve target dimensionality",
                            code="invalid_mapping_dimensions",
                            path=(*path, "binding", "args"),
                        )
                    if operation == "conform" and (
                        dataset.id not in unique_datasets
                        or any(
                            location.entity_id != entity_id
                            for location in input_locations
                            if location is not None
                        )
                    ):
                        raise errors.AnalyticsError(
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
                            if (
                                (location := validation_context.dataset(source_id)) is not None
                                and set(location.entity.dimension_ids) < target_dimensions
                            )
                        }
                        lower_dimensional_input = bool(lower_dataset_ids)
                        lower_dimensional_features = any(
                            (owner := validation_context.last_feature_owner(feature_id)) is not None
                            and owner.dataset.id in lower_dataset_ids
                            for feature_id in mapping.input_features
                        )
                        if (
                            not target_is_input
                            or not lower_dimensional_input
                            or not lower_dimensional_features
                        ):
                            raise errors.AnalyticsError(
                                "Expand mapping must combine its target dataset with a "
                                "declared feature from a lower-dimensional dataset",
                                code="invalid_mapping_dimensions",
                                path=(*path, "binding", "args"),
                            )
