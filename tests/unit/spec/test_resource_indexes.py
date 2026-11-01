import collections.abc
import typing

import pytest

from uptimely.spec import arg_types, model, selectors, validation


def _sample_spec() -> model.Spec:
    return model.Spec.model_validate(
        {
            "dimensions": {"key": {"type": "integer"}},
            "functions": {
                name: {
                    "kind": "read",
                    "returns": "dataframe",
                    "entrypoint": f"example:{name}",
                    "args": {"path": {"type": "str"}},
                }
                for name in ("load", "other")
            },
            "entities": {
                "entity": {
                    "name": "Entity",
                    "dimensions": ["key"],
                    "datasets": {
                        dataset: {
                            "features": {"key": {}, feature: {}},
                            "actions": {
                                "read": {
                                    "binding": {"function": function, "args": {"path": dataset}},
                                    "features": {
                                        "outputs": ["$features.key", f"$features.{feature}"]
                                    },
                                }
                            },
                        }
                        for dataset, feature, function in (
                            ("first", "value", "load"),
                            ("second", "another", "other"),
                        )
                    },
                }
            },
        }
    )


class _CountingDict(dict[str, typing.Any]):
    traversals = 0

    def items(self) -> collections.abc.ItemsView[str, typing.Any]:
        self.traversals += 1
        return super().items()

    def values(self) -> collections.abc.ValuesView[typing.Any]:
        self.traversals += 1
        return super().values()


class _CountingList(list[typing.Any]):
    traversals = 0

    def __iter__(self) -> collections.abc.Iterator[typing.Any]:
        self.traversals += 1
        return super().__iter__()


def test_resource_indexes_traverse_each_collection_once() -> None:
    document = _sample_spec()
    counted = []
    document.entities = _CountingDict(document.entities)
    counted.append(document.entities)
    for entity in document.entities.values():
        entity.datasets = _CountingDict(entity.datasets)
        counted.append(entity.datasets)
        for dataset in entity.datasets.values():
            dataset.features = _CountingDict(dataset.features)
            dataset.actions = _CountingDict(dataset.actions)
            counted.extend([dataset.features, dataset.actions])
    for function in document.functions.root.values():
        function.args = _CountingDict(function.args)
        counted.append(function.args)
    for collection in counted:
        collection.traversals = 0

    for _ in range(3):
        assert list(document.datasets) == ["first", "second"]
        assert list(document.features) == ["key", "value", "another"]
        assert list(document.actions_by_key) == [
            ("entity", "first", "read"),
            ("entity", "second", "read"),
        ]
        assert document.action_datasets == {
            ("entity", "first", "read"): document.datasets_by_key["entity", "first"],
            ("entity", "second", "read"): document.datasets_by_key["entity", "second"],
        }
        assert list(document.arguments) == [("load", "path"), ("other", "path")]
        assert document.dimension_ids_by_dataset == {"first": ["key"], "second": ["key"]}
        assert len(document.actions) == 2
        assert len(document.dataset_items) == 2
        assert document.actions_by_function["load"] == [("entity", "first", "read")]
        assert document.feature_producers["value"] == [("entity", "first", "read")]
        assert document.actions[0] is document.entities["entity"].datasets["first"].actions["read"]
        assert document.actions is document.actions
        assert document.features["value"] is document.datasets["first"].features["value"]

    assert all(collection.traversals == 1 for collection in counted)
    assert document.arguments["load", "path"] is document.functions["load"].args["path"]
    assert "key" not in document.feature_owners


def test_new_model_discovers_edits_without_invalidation_machinery() -> None:
    document = _sample_spec()
    previous = document.features
    assert document.arguments
    document.datasets["first"].features["new"] = model.Feature(id="new")
    document.functions["load"].args["extra"] = model.Argument(id="extra", type="str")
    assert "new" not in previous
    assert ("load", "extra") not in document.arguments
    reconstructed = model.Spec.model_validate(document.model_dump())
    assert reconstructed.features["new"] is reconstructed.datasets["first"].features["new"]
    assert ("load", "extra") in reconstructed.arguments
    reconstructed.entities["duplicate"] = reconstructed.entities["entity"].model_copy(deep=True)
    duplicate = model.Spec.model_validate(reconstructed.model_dump())
    with pytest.raises(ValueError, match="Duplicate dataset id"):
        validation.validate_spec(duplicate)
    assert len(duplicate.dataset_items) == 4
    assert len(duplicate.feature_owners["value"]) == 2


def test_indexes_preserve_action_aliases_and_diagnostic_paths() -> None:
    document = _sample_spec()
    action = document.entities["entity"].datasets["first"].actions["read"]
    document.entities["entity"].datasets["first"].actions["alias"] = action
    action.binding.function = "missing"
    key = ("entity", "first", "alias")
    assert document.actions_by_key[key] is action
    assert document.action_datasets[key] is document.datasets_by_key["entity", "first"]
    assert document.actions[:2] == [action, action]
    assert document.action_paths[key][-1] == "read"
    assert document.declaration_paths[key][-1] == "alias"
    assert action.binding.function not in document.functions


def test_nested_models_expose_cached_children_and_normalized_ids() -> None:
    document = _sample_spec()
    entity = document.entities["entity"]
    entity.dimensions = _CountingList(entity.dimensions)
    first = entity.datasets["first"]
    action = first.actions["read"]
    action.features.inputs = _CountingList(["$features.another"])
    action.features.outputs = _CountingList(action.features.outputs)
    first.order = _CountingList(
        [
            model.Order(dimension="$dimensions.key", direction="asc"),
            model.Order(dimension="$dimensions.key", direction="desc"),
        ]
    )
    document.functions["load"].args = _CountingDict(document.functions["load"].args)
    for _ in range(3):
        assert entity.dimension_ids == ["key"]
        assert entity.dimension_id_set == frozenset({"key"})
        assert entity.features["value"] is first.features["value"]
        assert entity.actions["first", "read"] is action
        assert entity.arguments["first", "read", "path"] == "first"
        assert first.arguments["read", "path"] == "first"
        assert action.arguments is action.binding.args
        assert first.feature_producers["value"] == (("read", action),)
        assert action.input_features is action.features.input_ids
        assert action.input_features == ["another"]
        assert action.output_features is action.features.output_ids
        assert action.output_features == ["key", "value"]
        assert first.order_dimensions == (("key", frozenset()), ("key", frozenset({"key"})))
        assert first.order_references == frozenset({"$dimensions.key"})
        assert (
            document.functions["load"].arguments_by_type["str"]["path"]
            is (document.functions["load"].args["path"])
        )
        assert document.functions.by_kind("read") is document.functions.by_kind("read")
    assert entity.dimensions.traversals == 1
    assert action.features.inputs.traversals == 1
    assert action.features.outputs.traversals == 1
    assert first.order.traversals == 1
    assert document.functions["load"].args.traversals == 1


def test_validation_views_reuse_one_nested_binding_traversal() -> None:
    document = _sample_spec()
    action = document.entities["entity"].datasets["first"].actions["read"]
    document.functions["load"].args = {
        "source": model.Argument(id="source", type=arg_types.DATAFRAME),
        "selection": model.Argument(
            id="selection", type=arg_types.object_values_of(arg_types.array_of(arg_types.STRING))
        ),
    }
    values = _CountingList(
        [
            "$features.another",
            "$dimensions.key",
            f"$datasets.second{selectors.DIMENSION_IDS_SELECTOR}",
            f"$datasets.@{selectors.DIMENSION_IDS_SELECTOR}",
            "$features.@.id",
            "$datasets.first.id",
            3,
            None,
        ]
    )
    selection = _CountingDict({"columns": values, "empty": []})
    arguments = _CountingDict(
        {
            "source": "$datasets.second.dataframe",
            "selection": selection,
            "unknown": "$features.value",
        }
    )
    action.binding.args = arguments
    action.features.inputs = ["$features.another"]
    key = ("entity", "first", "read")
    for _ in range(3):
        assert document.input_sources[key] == ("entity", "second")
        assert action.dataset_references == ("second", "second", "@", "first")
        assert action.binding.dataset_input_references == ("second",)
        assert action.binding.dataset_input_references is action.binding.dataset_input_references
        assert action.dataset_references is action.dataset_references
        assert action.feature_selectors == ("another", "@", "value")
        assert action.feature_selectors is action.feature_selectors
        assert action.dimensions_references == ("key",)
        assert action.dimensions_references is action.dimensions_references
        assert action.dimension_reference_paths == (("key", ("selection", "columns", 1)),)
        assert document.input_sources is document.input_sources
        assert document.action_dataset_keys[key] == ("entity", "first")
        assert document.dataset_argument_ids[key] == frozenset({"second"})
        assert document.dataset_argument_dimensions[key] == frozenset({"key"})
        assert document.dataset_argument_sources[key] == (("entity", "second"),)
        assert document.actions_arguments[key] == (
            ("source", "$datasets.second.dataframe", "second"),
        )
        assert document.matching_key_dimensions[key] == (
            (
                "key",
                (*document.declaration_paths[key], "binding", "args", "selection", "columns", 2),
            ),
            (
                "key",
                (*document.declaration_paths[key], "binding", "args", "selection", "columns", 3),
            ),
        )
        assert len(document.binding_selectors[key]) == 9
        assert document.binding_selectors[key][0] == (
            "$datasets.second.dataframe",
            arg_types.DATAFRAME,
        )
        assert document.binding_selectors[key][-1] == (None, arg_types.STRING)
        assert document.binding_selectors_with_paths == tuple(
            ((*document.declaration_paths[action_key], "binding", "args"), value, argument_type)
            for action_key, binding_values in document.binding_selectors.items()
            for value, argument_type in binding_values
        )
        assert document.binding_selectors_with_paths is document.binding_selectors_with_paths
        assert action.binding.references_by_prefix[selectors.FEATURE_PREFIX][0] == (
            "another",
            ("selection", "columns", 0),
        )
    assert arguments.traversals == selection.traversals == values.traversals == 1


def test_indexes_do_not_change_serialization() -> None:
    document = _sample_spec()
    before = document.model_dump(mode="json")
    assert document.features and document.actions and document.arguments
    assert document.input_sources and document.actions_arguments
    assert document.entities["entity"].features
    assert document.datasets["first"].feature_producers
    assert document.binding_selectors
    assert document.binding_selectors_with_paths
    assert document.matching_key_dimensions
    assert document.model_dump(mode="json") == before
    copied = model.Spec.model_validate(before)
    assert copied == document
    assert copied.actions[0] is copied.datasets["first"].actions["read"]
    assert copied.features["value"] is not document.features["value"]
    replaced = model.Spec.model_validate({**before, "entities": {}})
    assert replaced.features == replaced.datasets == replaced.actions_by_key == {}
    assert replaced.actions == replaced.dataset_items == []


def test_empty_spec_indexes() -> None:
    document = model.Spec()
    assert document.features == document.datasets == document.arguments == {}
    assert (
        document.actions_by_key
        == document.input_sources
        == document.actions_arguments
        == document.action_dataset_keys
        == document.action_datasets
        == document.matching_key_dimensions
        == {}
    )
    assert document.actions == document.action_items == document.dataset_items == []
    assert document.binding_selectors_with_paths == ()
    assert document.entrypoints == []


def test_entrypoints_are_distinct_strings_and_follow_catalog_edits() -> None:
    document = _sample_spec()
    functions = list(document.functions.root.values())
    assert document.entrypoints == [function.entrypoint for function in functions]
    functions[1].entrypoint = functions[0].entrypoint
    assert document.entrypoints == [functions[0].entrypoint]
    functions[1].entrypoint = "invalid-entrypoint"
    assert document.entrypoints == [functions[0].entrypoint, "invalid-entrypoint"]


def test_action_dataset_references_retain_unknown_ids_and_ignore_other_values() -> None:
    action = model.Action(
        id="action",
        binding=model.Binding(
            function="function",
            args={
                "nested": [
                    "$datasets.missing",
                    "$datasets.missing.id",
                    "$datasets.@.dataframe",
                    "$datasets.other.dimensions.ids",
                    "$features.value",
                    "literal",
                    None,
                    {},
                ],
            },
        ),
    )
    before = action.model_dump()
    assert action.dataset_references == ("missing", "missing", "@", "other")
    assert action.model_dump() == before
    assert (
        model.Action(id="empty", binding=model.Binding(function="function")).dataset_references
        == ()
    )


def test_action_dimension_references_preserve_ids_paths_and_serialization() -> None:
    action = model.Action(
        id="action",
        binding=model.Binding(
            function="function",
            args={
                "nested": {
                    "dimensions": [
                        "$dimensions.missing",
                        "$dimensions.missing.id",
                        "$dimensions.other",
                        "$datasets.source.dimensions.ids",
                        None,
                    ],
                },
            },
        ),
    )
    before = action.model_dump()
    assert action.dimensions_references == ("missing", "missing", "other")
    assert action.dimension_reference_paths == (
        ("missing", ("nested", "dimensions", 0)),
        ("missing", ("nested", "dimensions", 1)),
        ("other", ("nested", "dimensions", 2)),
    )
    assert action.dimension_reference_paths is action.dimension_reference_paths
    assert action.model_dump() == before
    empty = model.Action(id="empty", binding=model.Binding(function="function"))
    assert empty.dimensions_references == empty.dimension_reference_paths == ()


def test_action_feature_selectors_are_distinct_from_explicit_inputs() -> None:
    action = model.Action(
        id="action",
        binding=model.Binding(
            function="function",
            args={
                "nested": [
                    "$features.missing",
                    {"column": "$features.missing.id"},
                    "$features.@.id",
                    "$datasets.source.dataframe",
                    None,
                ],
            },
        ),
        features=model.ActionFeatures(inputs=["$features.input"]),
    )
    before = action.model_dump()
    assert action.feature_selectors == ("missing", "missing", "@")
    assert action.input_features == ["input"]
    assert action.model_dump() == before
    empty = model.Action(id="empty", binding=model.Binding(function="function"))
    assert empty.feature_selectors == ()
