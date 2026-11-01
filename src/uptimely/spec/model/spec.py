"""The spec document and its cached resource indexes."""

from __future__ import annotations

import dataclasses
import functools
import typing

import pydantic

from uptimely.spec import arg_types, functions, selectors

from . import common
from . import dataset as dataset_module
from . import functions as functions_module

SPEC_VERSION = 3
type DatasetKey = tuple[str, str]
type ActionKey = tuple[str, str, str]
type SpecPath = tuple[str | int, ...]
type DatasetArgument = tuple[str, object, str | None]


@dataclasses.dataclass
class _ResourceIndex:
    dataset_items: list[tuple[DatasetKey, dataset_module.Dataset]] = dataclasses.field(
        default_factory=list
    )
    action_items: list[tuple[ActionKey, dataset_module.Action]] = dataclasses.field(
        default_factory=list
    )
    datasets: dict[str, dataset_module.Dataset] = dataclasses.field(default_factory=dict)
    datasets_by_key: dict[DatasetKey, dataset_module.Dataset] = dataclasses.field(
        default_factory=dict
    )
    dataset_keys: dict[str, DatasetKey] = dataclasses.field(default_factory=dict)
    features: dict[str, dataset_module.Feature] = dataclasses.field(default_factory=dict)
    actions: list[dataset_module.Action] = dataclasses.field(default_factory=list)
    actions_by_key: dict[ActionKey, dataset_module.Action] = dataclasses.field(default_factory=dict)
    action_dataset_keys: dict[ActionKey, DatasetKey] = dataclasses.field(default_factory=dict)
    action_datasets: dict[ActionKey, dataset_module.Dataset] = dataclasses.field(
        default_factory=dict
    )
    feature_owners: dict[str, list[DatasetKey]] = dataclasses.field(default_factory=dict)
    actions_by_function: dict[str, list[ActionKey]] = dataclasses.field(default_factory=dict)
    feature_producers: dict[str, list[ActionKey]] = dataclasses.field(default_factory=dict)
    dimensions: dict[DatasetKey, frozenset[str]] = dataclasses.field(default_factory=dict)
    dimension_ids: dict[str, list[str]] = dataclasses.field(default_factory=dict)
    action_paths: dict[ActionKey, SpecPath] = dataclasses.field(default_factory=dict)
    declaration_paths: dict[ActionKey, SpecPath] = dataclasses.field(default_factory=dict)


class Spec(common.StrictModel):
    """The complete JSON document; cached views assume declarations are unchanged."""

    name: str | None = None
    spec_version: typing.Literal[3] = SPEC_VERSION
    source: common.SpecSource = pydantic.Field(
        default_factory=lambda: common.SpecSource(name="manual", generated=False)
    )
    dimensions: dict[str, common.Dimension] = pydantic.Field(default_factory=dict)
    functions: functions_module.FunctionCatalog = pydantic.Field(
        default_factory=functions_module.FunctionCatalog
    )
    entities: dict[str, dataset_module.Entity] = pydantic.Field(default_factory=dict)

    @functools.cached_property
    def _indexes(self) -> _ResourceIndex:
        indexes = _ResourceIndex()
        for entity_id, entity in self.entities.items():
            for dataset in entity.datasets.values():
                dataset_key = (entity_id, dataset.id)
                indexes.dataset_items.append((dataset_key, dataset))
                indexes.datasets[dataset.id] = dataset
                indexes.datasets_by_key[dataset_key] = dataset
                indexes.dataset_keys[dataset.id] = dataset_key
                indexes.dimensions[dataset_key] = entity.dimension_id_set
                indexes.dimension_ids[dataset.id] = entity.dimension_ids
                for feature_id, feature in dataset.features.items():
                    indexes.features[feature_id] = feature
                    if feature_id not in self.dimensions:
                        indexes.feature_owners.setdefault(feature_id, []).append(dataset_key)
                for action_id, action in dataset.actions.items():
                    key = (*dataset_key, action_id)
                    indexes.action_items.append((key, action))
                    indexes.actions.append(action)
                    indexes.actions_by_key[key] = action
                    indexes.action_dataset_keys[key] = dataset_key
                    indexes.action_datasets[key] = dataset
                    base = ("entities", entity_id, "datasets", dataset.id, "actions")
                    indexes.action_paths[key] = (*base, action.id)
                    indexes.declaration_paths[key] = (*base, action_id)
                    indexes.actions_by_function.setdefault(action.binding.function, []).append(key)
                    for feature_id in action.output_features:
                        indexes.feature_producers.setdefault(feature_id, []).append(key)
        return indexes

    @property
    def datasets(self) -> dict[str, dataset_module.Dataset]:
        """Return original dataset objects keyed by globally unique ID."""
        return self._indexes.datasets

    @property
    def dataset_items(self) -> list[tuple[DatasetKey, dataset_module.Dataset]]:
        """Return dataset occurrences with entity/ID keys, retaining duplicates."""
        return self._indexes.dataset_items

    @property
    def datasets_by_key(self) -> dict[DatasetKey, dataset_module.Dataset]:
        """Return datasets keyed by entity ID and dataset ID."""
        return self._indexes.datasets_by_key

    @property
    def dataset_keys(self) -> dict[str, DatasetKey]:
        """Return each global dataset ID's owning occurrence key."""
        return self._indexes.dataset_keys

    @property
    def features(self) -> dict[str, dataset_module.Feature]:
        """Return original feature metadata keyed by ID, including dimensions."""
        return self._indexes.features

    @property
    def actions(self) -> list[dataset_module.Action]:
        """Return original Action objects in declaration order, retaining aliases."""
        return self._indexes.actions

    @property
    def action_items(self) -> list[tuple[ActionKey, dataset_module.Action]]:
        """Return action occurrences with entity/dataset/dictionary keys."""
        return self._indexes.action_items

    @property
    def actions_by_key(self) -> dict[ActionKey, dataset_module.Action]:
        """Return original actions keyed by their declaration locations."""
        return self._indexes.actions_by_key

    @property
    def action_dataset_keys(self) -> dict[ActionKey, DatasetKey]:
        """Return each action's owning dataset occurrence key."""
        return self._indexes.action_dataset_keys

    @property
    def action_datasets(self) -> dict[ActionKey, dataset_module.Dataset]:
        """Return each action's owning dataset occurrence."""
        return self._indexes.action_datasets

    def _row_context_dataset_key(self, key: ActionKey) -> DatasetKey | None:
        """Resolve the dataset whose observations an action's context describes."""
        action = self.actions_by_key[key]
        function = self.functions[action.binding.function]
        definition = functions.FUNCTION_KINDS[function.kind]
        return (
            self.input_sources[key]
            if definition.dimension_change == "remove"
            else self.action_dataset_keys[key]
        )

    def get_row_context_dataset(self, key: ActionKey) -> dataset_module.Dataset | None:
        """Return the context dataset, or None when its source is unresolved."""
        source = self._row_context_dataset_key(key)
        return self.datasets_by_key[source] if source is not None else None

    def get_row_context_dimensions(self, key: ActionKey) -> frozenset[str] | None:
        """Return context entity dimension IDs, or None for an unresolved source."""
        source = self._row_context_dataset_key(key)
        return self.dimensions_by_dataset[source] if source is not None else None

    @property
    def arguments(self) -> dict[tuple[str, str], common.Argument]:
        """Return function argument declarations keyed by function and argument."""
        return self.functions.arguments

    @property
    def entrypoints(self) -> list[str]:
        """Return distinct catalog entrypoint strings in declaration order."""
        return list(dict.fromkeys(function.entrypoint for function in self.functions.root.values()))

    @property
    def feature_owners(self) -> dict[str, list[DatasetKey]]:
        """Return all occurrence keys owning each non-dimension feature."""
        return self._indexes.feature_owners

    @property
    def actions_by_function(self) -> dict[str, list[ActionKey]]:
        """Return action occurrence keys grouped by function ID."""
        return self._indexes.actions_by_function

    @property
    def feature_producers(self) -> dict[str, list[ActionKey]]:
        """Return all action occurrence keys declaring each output feature."""
        return self._indexes.feature_producers

    @property
    def dimensions_by_dataset(self) -> dict[DatasetKey, frozenset[str]]:
        """Return owning entity dimensions keyed by dataset occurrence."""
        return self._indexes.dimensions

    @property
    def dimension_ids_by_dataset(self) -> dict[str, list[str]]:
        """Return owning entity dimension IDs keyed by global dataset ID."""
        return self._indexes.dimension_ids

    @property
    def action_paths(self) -> dict[ActionKey, SpecPath]:
        """Return model-ID paths used by action contracts."""
        return self._indexes.action_paths

    @property
    def declaration_paths(self) -> dict[ActionKey, SpecPath]:
        """Return dictionary-key paths used by binding validation."""
        return self._indexes.declaration_paths

    @functools.cached_property
    def local_features(self) -> dict[DatasetKey, frozenset[str]]:
        """Return feature IDs available in each dataset, including dimensions."""
        return {
            key: frozenset(dataset.features) | self.dimensions_by_dataset[key]
            for key, dataset in self.dataset_items
        }

    @functools.cached_property
    def input_candidates(self) -> dict[ActionKey, tuple[tuple[str, list[DatasetKey]], ...]]:
        """Return ordered input feature owners, preserving unresolved and ambiguous inputs."""
        return {
            key: tuple(
                (feature, self.feature_owners.get(feature, []))
                for feature in action.input_features
                if feature != selectors.CURRENT_ID and feature not in self.dimensions
            )
            for key, action in self.action_items
        }

    @functools.cached_property
    def input_sources(self) -> dict[ActionKey, DatasetKey | None]:
        """Return the unique source occurrence for each action, or None when unresolved."""
        result: dict[ActionKey, DatasetKey | None] = {}
        for key, candidates in self.input_candidates.items():
            sources = {owners[0][1]: owners[0] for _, owners in candidates if len(owners) == 1}
            result[key] = (
                next(iter(sources.values()))
                if len(sources) == 1 and all(len(owners) == 1 for _, owners in candidates)
                else None
            )
        return result

    @functools.cached_property
    def actions_arguments(self) -> dict[ActionKey, tuple[DatasetArgument, ...]]:
        """Return supplied dataset arguments and normalized dataset IDs per action."""
        result: dict[ActionKey, tuple[DatasetArgument, ...]] = {}
        for key, action in self.action_items:
            function = self.functions.root.get(action.binding.function)
            arguments: list[DatasetArgument] = []
            if function is not None:
                for name in function.arguments_by_type.get(arg_types.DATAFRAME, {}):
                    value = action.arguments.get(name)
                    source_id = None
                    if isinstance(value, str) and value.startswith(selectors.DATASET_PREFIX):
                        reference = value.removeprefix(selectors.DATASET_PREFIX).removesuffix(
                            selectors.DATAFRAME_SELECTOR
                        )
                        source_id = key[1] if reference == selectors.CURRENT_ID else reference
                    arguments.append((name, value, source_id))
            result[key] = tuple(arguments)
        return result

    @functools.cached_property
    def dataset_argument_sources(self) -> dict[ActionKey, tuple[DatasetKey, ...]]:
        """Return resolved dataset argument occurrences in argument order."""
        return {
            key: tuple(
                self.dataset_keys[source_id]
                for _, _, source_id in arguments
                if source_id is not None and source_id in self.dataset_keys
            )
            for key, arguments in self.actions_arguments.items()
        }

    @functools.cached_property
    def dataset_argument_ids(self) -> dict[ActionKey, frozenset[str]]:
        """Return distinct resolved dataset argument IDs per action."""
        return {
            key: frozenset(source[1] for source in sources)
            for key, sources in self.dataset_argument_sources.items()
        }

    @functools.cached_property
    def dataset_argument_dimensions(self) -> dict[ActionKey, frozenset[str]]:
        """Return dimensions available across each action's dataset arguments."""
        return {
            key: frozenset().union(*(self.dimensions_by_dataset[source] for source in sources))
            for key, sources in self.dataset_argument_sources.items()
        }

    @functools.cached_property
    def binding_selectors(self) -> dict[ActionKey, tuple[tuple[object, str], ...]]:
        """Return supplied binding leaves with their inherited argument types."""
        result: dict[ActionKey, tuple[tuple[object, str], ...]] = {}
        for key, action in self.action_items:
            values: list[tuple[object, str]] = []
            function = self.functions.root.get(action.binding.function)
            if function is not None:
                for value, path in action.binding.values_with_paths:
                    argument = function.args.get(path[0]) if isinstance(path[0], str) else None
                    if argument is None:
                        continue
                    argument_type = argument.type
                    for segment in path[1:]:
                        item_type = (
                            arg_types.array_item_type(argument_type)
                            if isinstance(segment, int)
                            else arg_types.object_value_type(argument_type)
                        )
                        argument_type = item_type or arg_types.STRING
                    values.append((value, argument_type))
            result[key] = tuple(values)
        return result

    @functools.cached_property
    def binding_selectors_with_paths(self) -> tuple[tuple[SpecPath, object, str], ...]:
        """Return binding leaves and argument types with their binding argument paths."""
        return tuple(
            ((*self.declaration_paths[key], "binding", "args"), value, argument_type)
            for key, values in self.binding_selectors.items()
            for value, argument_type in values
        )

    @functools.cached_property
    def matching_key_dimensions(self) -> dict[ActionKey, tuple[tuple[str, SpecPath], ...]]:
        """Return selected matching dimensions and their declaration paths."""
        result: dict[ActionKey, tuple[tuple[str, SpecPath], ...]] = {}
        for key, action in self.action_items:
            matches: list[tuple[str, SpecPath]] = []
            for value, path in action.binding.values_with_paths:
                if not (
                    isinstance(value, str)
                    and value.startswith(selectors.DATASET_PREFIX)
                    and value.endswith(selectors.DIMENSION_IDS_SELECTOR)
                ):
                    continue
                dataset_id = value.removeprefix(selectors.DATASET_PREFIX).removesuffix(
                    selectors.DIMENSION_IDS_SELECTOR
                )
                if dataset_id == selectors.CURRENT_ID:
                    dataset_key = self.action_dataset_keys[key]
                else:
                    dataset_key = self.dataset_keys.get(dataset_id)
                if dataset_key is None:
                    continue
                matches.extend(
                    (dimension, (*self.declaration_paths[key], "binding", "args", *path))
                    for dimension in self.entities[dataset_key[0]].dimension_ids
                )
            result[key] = tuple(matches)
        return result

    @pydantic.field_validator("spec_version", mode="before")
    @classmethod
    def validate_spec_version_type(cls, value: object) -> object:
        """Reject booleans, which Python otherwise treats as integer literals."""
        if type(value) is not int:
            raise ValueError("spec_version must be an integer")
        return value

    @pydantic.model_validator(mode="before")
    @classmethod
    def normalize_document(cls, value: typing.Any) -> typing.Any:
        """Recover keyed resource IDs and resolve entity dimension references."""
        if not isinstance(value, dict):
            return value

        normalized = dict(value)
        normalized["dimensions"] = cls._with_resource_ids(normalized.get("dimensions", {}) or {})
        if "functions" in normalized:
            normalized["functions"] = cls._normalize_functions(normalized["functions"] or {})
        if "entities" in normalized:
            normalized["entities"] = cls._normalize_entities(
                normalized["entities"] or {}, normalized["dimensions"]
            )
        return normalized

    @classmethod
    def _normalize_functions(cls, value: typing.Any) -> typing.Any:
        """Recover function and argument IDs from their object keys."""
        functions = cls._with_resource_ids(value)
        if isinstance(functions, dict):
            for function in functions.values():
                if isinstance(function, dict):
                    function["args"] = cls._with_resource_ids(function.get("args", {}) or {})
        return functions

    @classmethod
    def _normalize_entities(cls, value: typing.Any, dimensions: typing.Any) -> typing.Any:
        """Recover entity IDs and normalize each entity's dimensions and datasets."""
        entities = cls._with_resource_ids(value)
        if isinstance(entities, dict):
            for entity in entities.values():
                if isinstance(entity, dict):
                    cls._normalize_entity(entity, dimensions)
        return entities

    @classmethod
    def _normalize_entity(cls, entity: dict[str, typing.Any], dimensions: typing.Any) -> None:
        """Resolve dimension IDs and recover the entity's nested dataset IDs."""
        entity["dimensions"] = [
            dimensions.get(dimension, dimension) if isinstance(dimension, str) else dimension
            for dimension in entity.get("dimensions", []) or []
        ]
        datasets = entity.get("datasets", {})
        if not isinstance(datasets, dict):
            return
        for dataset_id, dataset in datasets.items():
            if isinstance(dataset, dict) and "id" in dataset:
                raise ValueError(
                    f"Dataset {dataset_id} must use its object key as identifier, "
                    "not an 'id' attribute"
                )
        entity["datasets"] = cls._normalize_datasets(datasets)

    @classmethod
    def _normalize_datasets(cls, value: dict[str, typing.Any]) -> dict[str, typing.Any]:
        """Recover dataset, feature, and action IDs from their object keys."""
        datasets = cls._with_resource_ids(value)
        for dataset in datasets.values():
            if isinstance(dataset, dict):
                dataset["features"] = cls._with_resource_ids(dataset.get("features", {}) or {})
                dataset["actions"] = cls._with_resource_ids(dataset.get("actions", {}) or {})
        return datasets

    @staticmethod
    def _with_resource_ids(value: typing.Any) -> typing.Any:
        """Add object keys as IDs before Pydantic validates keyed resources."""
        if not isinstance(value, dict):
            return value
        return {
            key: dict(item) | {"id": key} if isinstance(item, dict) else item
            for key, item in value.items()
        }
