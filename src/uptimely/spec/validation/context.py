"""Per-invocation preparation, ordered declaration facts, and validation interface.

Preparation retains unresolved references and duplicate candidates. It never
raises semantic validation errors; domain rules decide which facts are invalid.
"""

from __future__ import annotations

import dataclasses
import functools
import typing

from uptimely.spec import model as spec_model
from uptimely.spec import references

from .. import arg_types, operations, selectors

type SpecPath = tuple[str | int, ...]
type MappingKey = tuple[str, str]
type ValidationResult = ValueError | None
type OutputDeclaration = tuple[str, str | None]
type MappingOutputFacts = tuple[MappingFacts, tuple[OutputDeclaration, ...]]
type DatasetOutputFacts = tuple[DatasetLocation, tuple[MappingOutputFacts, ...], tuple[str, ...]]


@dataclasses.dataclass(frozen=True)
class DatasetLocation:
    """A dataset and the entity declaring it, also used for owners and sources."""

    entity_id: str
    entity: spec_model.Entity
    dataset: spec_model.Dataset
    dimensions: frozenset[str]

    @property
    def key(self) -> tuple[str, str]:
        """Return the entity and dataset identity."""
        return self.entity_id, self.dataset.id

    @property
    def path(self) -> SpecPath:
        """Return the dataset's semantic path."""
        return ("entities", self.entity_id, "datasets", self.dataset.id)


@dataclasses.dataclass(frozen=True)
class MappingLocation:
    """A mapping location retaining dictionary-key and model-ID identities."""

    dataset_location: DatasetLocation
    mapping_id: str
    mapping: spec_model.Mapping

    @property
    def entity_id(self) -> str:
        """Return the declaring entity ID."""
        return self.dataset_location.entity_id

    @property
    def entity(self) -> spec_model.Entity:
        """Return the declaring entity."""
        return self.dataset_location.entity

    @property
    def dataset(self) -> spec_model.Dataset:
        """Return the declared dataset."""
        return self.dataset_location.dataset

    @property
    def key(self) -> tuple[str, str, str]:
        """Return the declaration identity."""
        return (*self.dataset_location.key, self.mapping_id)

    @property
    def path(self) -> SpecPath:
        """Return the model-ID path used by mapping contracts."""
        return (*self.dataset_location.path, "mappings", self.mapping.id)

    @property
    def declaration_path(self) -> SpecPath:
        """Return the dictionary-key path used by bindings."""
        return (*self.path[:-1], self.mapping_id)


@dataclasses.dataclass(frozen=True)
class OrderDimension:
    """One order declaration with its normalized identifier and preceding keys."""

    location: DatasetLocation
    dimension_id: str
    entity_dimensions: frozenset[str]
    preceding: frozenset[str]
    path: SpecPath


@dataclasses.dataclass(frozen=True)
class DimensionParents:
    """A dimension's parent and any cycle reached by walking its ancestry."""

    dimension_id: str
    parent_id: str | None
    cycle: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class MappingFacts:
    """Shared normalized mapping declarations and extracted structural references."""

    location: MappingLocation
    function: spec_model.FunctionTemplate | None
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    feature_references: tuple[str, ...]
    dataset_references: tuple[str, ...]
    dimension_references: tuple[str, ...]

    @property
    def dimensions(self) -> frozenset[str]:
        """Return the dimensions declared by this mapping's entity."""
        return self.location.dataset_location.dimensions

    @property
    def local_features(self) -> frozenset[str]:
        """Return the dataset's features together with its entity dimensions."""
        return frozenset(self.location.dataset.features) | self.dimensions

    @property
    def operation(self) -> operations.FunctionOperation | None:
        """Return the declared operation without requiring function resolution."""
        return self.function.operation if self.function is not None else None


@dataclasses.dataclass(frozen=True)
class CollapseInputs:
    """Ordered source candidates, including unresolved or ambiguous inputs."""

    mapping: MappingFacts
    candidates: tuple[tuple[str, tuple[DatasetLocation, ...]], ...]
    sources: tuple[DatasetLocation, ...]
    source: DatasetLocation | None
    source_features: frozenset[str]
    source_dimensions: frozenset[str]


@dataclasses.dataclass(frozen=True)
class RowContext:
    """Normalized row-context requirements against the selected input dataset."""

    mapping_id: str
    requires_order: bool
    has_order: bool
    dimension_reference: str | None
    dimension_id: str | None
    dimensions: frozenset[str]
    expected_type: str | None
    actual_type: str | None
    order_dimensions: frozenset[str]


@dataclasses.dataclass(frozen=True)
class DataframeInput:
    """A dataframe argument's value, normalized reference, and candidate source."""

    argument_id: str
    value: object
    source_id: str | None
    source: DatasetLocation | None
    path: SpecPath


@dataclasses.dataclass(frozen=True)
class MappingContract:
    """Prepared dataframe and dimensional relationships for an operation."""

    mapping: MappingFacts
    dataframe_arguments: tuple[DataframeInput, ...]
    dataset_ids: frozenset[str]
    source: DatasetLocation | None
    source_dimensions: frozenset[str]
    unavailable_features: tuple[str, ...]
    local_foreign_features: tuple[str, ...]
    input_dimensions: tuple[frozenset[str], ...]
    feature_dataset_ids: frozenset[str]
    target_is_input: bool
    lower_dataset_ids: frozenset[str]
    has_lower_feature: bool


@dataclasses.dataclass(frozen=True)
class SpecValidationContext:
    """Fresh, non-validating preparation shared by read-only domain checks.

    Cached facts belong to this invocation, not the document. Frozen dataclasses
    are shallowly immutable; the document must not be edited during validation.
    """

    model: spec_model.Spec
    dimension_ids: frozenset[str]
    datasets: tuple[DatasetLocation, ...]
    datasets_by_id: dict[str, tuple[DatasetLocation, ...]]
    feature_names: frozenset[str]
    feature_owners: dict[str, tuple[DatasetLocation, ...]]
    mappings: tuple[MappingFacts, ...]
    duplicate_dataset: tuple[DatasetLocation, DatasetLocation] | None
    duplicate_feature: str | None

    @classmethod
    def build(cls, model: spec_model.Spec) -> SpecValidationContext:
        """Collect shared declarations without rejecting duplicates or missing functions."""
        dimension_ids = frozenset(model.dimensions)
        datasets: list[DatasetLocation] = []
        datasets_by_id: dict[str, list[DatasetLocation]] = {}
        feature_names: set[str] = set()
        owners: dict[str, list[DatasetLocation]] = {}
        duplicate_dataset = None
        duplicate_feature = None
        mappings: list[MappingFacts] = []
        for entity_id, entity in model.entities.items():
            for dataset in entity.datasets.values():
                location = DatasetLocation(
                    entity_id, entity, dataset, frozenset(entity.dimension_ids)
                )
                datasets.append(location)
                dataset_candidates = datasets_by_id.setdefault(dataset.id, [])
                if duplicate_dataset is None and dataset_candidates:
                    duplicate_dataset = location, dataset_candidates[0]
                dataset_candidates.append(location)
                feature_names.update(dataset.features)
                for feature_id in dataset.features:
                    if feature_id not in dimension_ids:
                        feature_candidates = owners.setdefault(feature_id, [])
                        if duplicate_feature is None and feature_candidates:
                            duplicate_feature = feature_id
                        feature_candidates.append(location)
                for mapping_id, mapping in dataset.mappings.items():
                    mappings.append(
                        MappingFacts(
                            location=MappingLocation(location, mapping_id, mapping),
                            function=model.functions.get(mapping.binding.function),
                            inputs=tuple(mapping.input_features),
                            outputs=tuple(mapping.output_features),
                            feature_references=tuple(
                                references.structural_references(
                                    mapping.binding.args, selectors.FEATURE_PREFIX
                                )
                            ),
                            dataset_references=tuple(
                                references.structural_references(
                                    mapping.binding.args, selectors.DATASET_PREFIX
                                )
                            ),
                            dimension_references=tuple(
                                references.structural_references(
                                    mapping.binding.args, selectors.DIMENSION_PREFIX
                                )
                            ),
                        )
                    )
        return cls(
            model=model,
            dimension_ids=dimension_ids,
            datasets=tuple(datasets),
            datasets_by_id={key: tuple(value) for key, value in datasets_by_id.items()},
            feature_names=frozenset(feature_names) | dimension_ids,
            feature_owners={key: tuple(value) for key, value in owners.items()},
            mappings=tuple(mappings),
            duplicate_dataset=duplicate_dataset,
            duplicate_feature=duplicate_feature,
        )

    def iter_mappings(self) -> typing.Iterator[MappingLocation]:
        """Yield mapping locations in declaration order."""
        return (item.location for item in self.mappings)

    def dataset(self, dataset_id: str) -> DatasetLocation | None:
        """Return the last candidate, matching historical catalog indexing."""
        candidates = self.datasets_by_id.get(dataset_id, ())
        return candidates[-1] if candidates else None

    def first_feature_owner(self, feature_id: str) -> DatasetLocation | None:
        """Return the first owner, matching early dependency validation."""
        candidates = self.feature_owners.get(feature_id, ())
        return candidates[0] if candidates else None

    def last_feature_owner(self, feature_id: str) -> DatasetLocation | None:
        """Return the last owner, matching mapping contract lookup."""
        candidates = self.feature_owners.get(feature_id, ())
        return candidates[-1] if candidates else None

    @functools.cached_property
    def order_dimensions(self) -> tuple[OrderDimension, ...]:
        """Normalize order keys and retain preceding dimensions for each key."""
        result: list[OrderDimension] = []
        for location in self.datasets:
            preceding: set[str] = set()
            for index, key in enumerate(location.dataset.order):
                dimension_id = key.dimension.removeprefix(selectors.DIMENSION_PREFIX)
                result.append(
                    OrderDimension(
                        location=location,
                        dimension_id=dimension_id,
                        entity_dimensions=location.dimensions,
                        preceding=frozenset(preceding),
                        path=(*location.path, "order", index, "dimension"),
                    )
                )
                preceding.add(dimension_id)
        return tuple(result)

    @functools.cached_property
    def dimension_parents(self) -> tuple[DimensionParents, ...]:
        """Walk parent chains, stopping at missing declarations or repeated endpoints."""
        result: list[DimensionParents] = []
        for dimension_id, dimension in self.model.dimensions.items():
            chain: list[str] = []
            current: str | None = dimension_id
            while current is not None and current not in chain:
                chain.append(current)
                declaration = self.model.dimensions.get(current)
                current = declaration.parent if declaration is not None else None
            cycle = tuple(chain[chain.index(current) :] + [current]) if current is not None else ()
            result.append(DimensionParents(dimension_id, dimension.parent, cycle))
        return tuple(result)

    def iter_entity_dimensions(self) -> typing.Iterator[tuple[str, frozenset[str]]]:
        """Yield normalized entity dimensions in declaration order."""
        return (
            (entity_id, frozenset(entity.dimension_ids))
            for entity_id, entity in self.model.entities.items()
        )

    def iter_calculation_dependencies(
        self,
    ) -> typing.Iterator[tuple[MappingFacts, str, DatasetLocation | None]]:
        """Yield vectorize input owners in mapping and input declaration order."""
        return (
            (item, feature_id, self.first_feature_owner(feature_id))
            for item in self.mappings
            if item.operation == operations.VECTORIZE
            for feature_id in item.inputs
        )

    def iter_write_dependencies(
        self,
    ) -> typing.Iterator[tuple[MappingFacts, tuple[str, ...]]]:
        """Yield foreign write inputs using first-owner lookup."""
        return (
            (
                item,
                tuple(
                    sorted(
                        feature_id
                        for feature_id in set(item.inputs) - item.dimensions
                        if (owner := self.first_feature_owner(feature_id)) is None
                        or owner.key != (item.location.entity_id, item.location.dataset.id)
                    )
                ),
            )
            for item in self.mappings
            if item.operation == operations.WRITE
        )

    def iter_output_datasets(
        self,
    ) -> typing.Iterator[DatasetOutputFacts]:
        """Yield each dataset's mapping outputs and uncovered features in declaration order."""
        offset = 0
        for location in self.datasets:
            producers: dict[str, str] = {}
            mappings: list[MappingOutputFacts] = []
            count = len(location.dataset.mappings)
            for item in self.mappings[offset : offset + count]:
                declarations: list[tuple[str, str | None]] = []
                if item.operation != operations.WRITE:
                    for feature_id in item.outputs:
                        declarations.append((feature_id, producers.get(feature_id)))
                        if feature_id not in item.dimensions:
                            producers[feature_id] = item.location.mapping_id
                mappings.append((item, tuple(declarations)))
            offset += count
            missing = tuple(
                sorted(set(location.dataset.features) - producers.keys() - location.dimensions)
            )
            yield location, tuple(mappings), missing

    @functools.cached_property
    def feature_producers(self) -> dict[str, MappingKey]:
        """Build the dependency producer index independently of output validity."""
        return {
            feature_id: (item.location.dataset.id, item.location.mapping_id)
            for item in self.mappings
            if item.operation != operations.WRITE
            for feature_id in item.outputs
            if feature_id not in item.dimensions and feature_id not in self.dimension_ids
        }

    @functools.cached_property
    def collapse_inputs(self) -> tuple[CollapseInputs, ...]:
        """Retain source candidates; unresolved inputs do not raise during preparation."""
        return self._prepare_collapse_inputs()

    def _prepare_collapse_inputs(self) -> tuple[CollapseInputs, ...]:
        """Infer all collapse source candidates once for this invocation."""
        result: list[CollapseInputs] = []
        for item in self.mappings:
            if item.operation != operations.COLLAPSE:
                continue
            candidates = tuple(
                (feature_id, self.feature_owners.get(feature_id, ()))
                for feature_id in item.inputs
                if feature_id != selectors.CURRENT_ID and feature_id not in self.dimension_ids
            )
            sources = {
                owners[0].dataset.id: owners[0] for _, owners in candidates if len(owners) == 1
            }
            source = (
                next(iter(sources.values()))
                if len(sources) == 1 and all(len(owners) == 1 for _, owners in candidates)
                else None
            )
            result.append(
                CollapseInputs(
                    mapping=item,
                    candidates=candidates,
                    sources=tuple(sources.values()),
                    source=source,
                    source_features=frozenset(source.dataset.features) | source.dimensions
                    if source is not None
                    else frozenset(),
                    source_dimensions=source.dimensions if source is not None else frozenset(),
                )
            )
        return tuple(result)

    @functools.cached_property
    def collapse_sources(self) -> dict[tuple[str, str, str], DatasetLocation]:
        """Share inferred source locations across row context and mapping contracts."""
        return {
            item.mapping.location.key: item.source
            for item in self.collapse_inputs
            if item.source is not None
        }

    def row_context(self, item: MappingFacts) -> RowContext | None:
        """Prepare row-context facts against the collapse source or local dataset."""
        declaration = item.location.mapping.row_context
        if declaration is None:
            return None
        source = (
            self.collapse_sources.get(item.location.key)
            if item.operation == operations.COLLAPSE
            else item.location.dataset_location
        )
        if source is None:
            return None
        reference = declaration.dimension
        dimension_id = reference.removeprefix(selectors.DIMENSION_PREFIX) if reference else None
        dimension = self.model.dimensions.get(dimension_id) if dimension_id is not None else None
        measures = {
            measure
            for direction in (declaration.before, declaration.after)
            if hasattr(direction, "model_dump")
            for measure in direction.model_dump(exclude_none=True)
        }
        expected = ("datetime" if "time" in measures else "integer") if measures else None
        return RowContext(
            mapping_id=item.location.mapping.id,
            requires_order=declaration.requires_order,
            has_order=bool(source.dataset.order),
            dimension_reference=reference,
            dimension_id=dimension_id,
            dimensions=source.dimensions,
            expected_type=expected,
            actual_type=dimension.type if dimension is not None else None,
            order_dimensions=frozenset(key.dimension for key in source.dataset.order),
        )

    def iter_input_contexts(
        self,
    ) -> typing.Iterator[tuple[MappingFacts, RowContext | None]]:
        """Yield each mapping with its row-context requirements in declaration order."""
        return ((item, self.row_context(item)) for item in self.mappings)

    @functools.cached_property
    def mapping_dependencies(self) -> dict[MappingKey, set[MappingKey]]:
        """Build mapping dependencies using model-ID consumers and declaration-key producers."""
        return {
            (item.location.dataset.id, item.location.mapping.id): {
                self.feature_producers[feature_id]
                for feature_id in item.inputs
                if feature_id in self.feature_producers
            }
            for item in self.mappings
        }

    @functools.cached_property
    def mapping_cycle(self) -> MappingKey | None:
        """Find the first active dependency reached by the established DFS order."""
        visiting: set[MappingKey] = set()
        visited: set[MappingKey] = set()

        def visit(key: MappingKey) -> MappingKey | None:
            if key in visiting:
                return key
            if key in visited:
                return None
            visiting.add(key)
            for dependency in self.mapping_dependencies[key]:
                cycle = visit(dependency)
                if cycle is not None:
                    return cycle
            visiting.remove(key)
            visited.add(key)
            return None

        for key in self.mapping_dependencies:
            cycle = visit(key)
            if cycle is not None:
                return cycle
        return None

    @staticmethod
    def _binding_selectors(
        value: object, argument_type: str
    ) -> typing.Iterator[tuple[object, str]]:
        """Flatten nested binding values with their inherited argument types."""
        if isinstance(value, list):
            element_type = arg_types.array_item_type(argument_type) or arg_types.STRING
            for item in value:
                yield from SpecValidationContext._binding_selectors(item, element_type)
        elif isinstance(value, dict):
            value_type = arg_types.object_value_type(argument_type) or arg_types.STRING
            for item in value.values():
                yield from SpecValidationContext._binding_selectors(item, value_type)
        else:
            yield value, argument_type

    def iter_bound_mappings(self) -> typing.Iterator[MappingFacts]:
        """Yield mappings whose declared function is available for binding checks."""
        return (item for item in self.mappings if item.function is not None)

    @classmethod
    def iter_binding_selectors(cls, item: MappingFacts) -> typing.Iterator[tuple[object, str]]:
        """Yield supplied selector values paired with their declared argument types."""
        if item.function is None:
            return
        for name, value in item.location.mapping.binding.args.items():
            argument = item.function.args.get(name)
            if argument is not None:
                yield from cls._binding_selectors(value, argument.type)

    def iter_functions(
        self,
    ) -> typing.Iterator[tuple[str, spec_model.FunctionTemplate, int]]:
        """Yield each function with its dataframe-argument count."""
        return (
            (
                function_id,
                function,
                sum(argument.type == arg_types.DATAFRAME for argument in function.args.values()),
            )
            for function_id, function in self.model.functions.root.items()
        )

    def _dataframe_inputs(self, item: MappingFacts) -> tuple[DataframeInput, ...]:
        """Retain dataframe selector values and any matching dataset without rejecting them."""
        if item.function is None:
            return ()
        result: list[DataframeInput] = []
        for argument_id, argument in item.function.args.items():
            if argument.type != arg_types.DATAFRAME:
                continue
            value = item.location.mapping.binding.args.get(argument_id)
            source_id = None
            if isinstance(value, str) and value.startswith(selectors.DATASET_PREFIX):
                reference = value.removeprefix(selectors.DATASET_PREFIX).removesuffix(
                    selectors.DATAFRAME_SELECTOR
                )
                source_id = (
                    item.location.dataset.id if reference == selectors.CURRENT_ID else reference
                )
            source = self.dataset(source_id) if source_id is not None else None
            result.append(
                DataframeInput(
                    argument_id,
                    value,
                    source_id,
                    source,
                    (*item.location.path, "binding", "args", argument_id),
                )
            )
        return tuple(result)

    @functools.cached_property
    def mapping_contracts(self) -> tuple[MappingContract, ...]:
        """Prepare dataframe relationships and ownership for operation-specific checks."""
        return tuple(self._mapping_contract(item) for item in self.mappings)

    def _mapping_contract(self, item: MappingFacts) -> MappingContract:
        """Collect the dataframe relationships used by one mapping's contract rules."""
        dataframe_arguments = self._dataframe_inputs(item)
        inputs = tuple(
            argument.source for argument in dataframe_arguments if argument.source is not None
        )
        dataset_ids = frozenset(source.dataset.id for source in inputs)
        input_dimensions = tuple(source.dimensions for source in inputs)
        available_dimensions = frozenset().union(*input_dimensions)
        unavailable_features = tuple(
            sorted(
                feature
                for feature in item.inputs
                if self._feature_unavailable(feature, dataset_ids, available_dimensions)
            )
        )
        lower_dataset_ids = frozenset(
            source.dataset.id for source in inputs if source.dimensions < item.dimensions
        )
        feature_dataset_ids = frozenset(
            owner.dataset.id
            for feature in item.inputs
            if feature not in self.dimension_ids
            and feature != selectors.CURRENT_ID
            and (owner := self.last_feature_owner(feature)) is not None
        )
        source = self.collapse_sources.get(item.location.key)
        return MappingContract(
            mapping=item,
            dataframe_arguments=dataframe_arguments,
            dataset_ids=dataset_ids,
            source=source,
            source_dimensions=source.dimensions if source is not None else frozenset(),
            unavailable_features=unavailable_features,
            local_foreign_features=tuple(
                sorted(feature for feature in item.inputs if feature not in item.local_features)
            ),
            input_dimensions=input_dimensions,
            feature_dataset_ids=feature_dataset_ids,
            target_is_input=item.location.dataset.id in dataset_ids,
            lower_dataset_ids=lower_dataset_ids,
            has_lower_feature=self._has_lower_feature(item.inputs, lower_dataset_ids),
        )

    def _feature_unavailable(
        self,
        feature: str,
        dataset_ids: frozenset[str],
        available_dimensions: frozenset[str],
    ) -> bool:
        """Return whether an input feature is absent from its supplied dataframes."""
        if feature in self.dimension_ids:
            return feature not in available_dimensions
        owner = self.last_feature_owner(feature)
        return owner is None or owner.dataset.id not in dataset_ids

    def _has_lower_feature(
        self, features: tuple[str, ...], lower_dataset_ids: frozenset[str]
    ) -> bool:
        """Return whether an input feature belongs to a lower-dimensional dataset."""
        return any(
            (owner := self.last_feature_owner(feature)) is not None
            and owner.dataset.id in lower_dataset_ids
            for feature in features
        )
