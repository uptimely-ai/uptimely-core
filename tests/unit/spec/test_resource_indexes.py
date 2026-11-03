import collections.abc
import typing

import pytest

from uptimely.spec import model, validation


def _sample_spec() -> model.Spec:
    return model.Spec.model_validate(
        {
            "dimensions": {"key": {"resolutions": {"key": {"key": "key", "type": "integer"}}}},
            "functions": {
                name: {
                    "kind": "read",
                    "returns": "dataframe",
                    "entrypoint": f"example:{name}",
                    "args": {"path": {"type": "str"}},
                }
                for name in ("load", "other")
            },
            "profiles": {
                profile: {
                    "grain": [{"dimension": "key", "resolution": "key"}],
                    "features": {"key": {}, feature: {}},
                    "actions": {
                        "read": {
                            "binding": {"function": function, "args": {"path": profile}},
                            "features": {"outputs": ["$features.key", f"$features.{feature}"]},
                        }
                    },
                }
                for profile, feature, function in (
                    ("first", "value", "load"),
                    ("second", "another", "other"),
                )
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


def test_resource_indexes_traverse_each_collection_once() -> None:
    document = _sample_spec()
    counted = []
    document.profiles = _CountingDict(document.profiles)
    counted.append(document.profiles)
    for profile in document.profiles.values():
        profile.features = _CountingDict(profile.features)
        profile.actions = _CountingDict(profile.actions)
        counted.extend([profile.features, profile.actions])
    for function in document.functions.root.values():
        function.args = _CountingDict(function.args)
        counted.append(function.args)
    for collection in counted:
        collection.traversals = 0

    for _ in range(3):
        assert list(document.profiles) == ["first", "second"]
        assert list(document.features) == ["key", "value", "another"]
        assert list(document.actions_by_key) == [("first", "read"), ("second", "read")]
        assert document.action_profiles == {
            ("first", "read"): document.profiles_by_key["first"],
            ("second", "read"): document.profiles_by_key["second"],
        }
        assert list(document.arguments) == [("load", "path"), ("other", "path")]
        assert document.grain_keys_by_profile == {"first": ["key"], "second": ["key"]}
        assert len(document.actions) == 2
        assert len(document.profile_items) == 2
        assert document.actions_by_function["load"] == [("first", "read")]
        assert document.feature_producers["value"] == [("first", "read")]
        assert document.actions[0] is document.profiles["first"].actions["read"]
        assert document.actions is document.actions
        assert document.features["value"] is document.profiles["first"].features["value"]

    assert all(collection.traversals == 1 for collection in counted)
    assert document.arguments["load", "path"] is document.functions["load"].args["path"]
    assert "key" not in document.feature_owners


def test_profiles_keep_only_their_own_dimension_context() -> None:
    document = _sample_spec()
    first = document.profiles["first"]
    assert first.dimension_ids == ["key"]
    assert first.features["value"].id == "value"
    assert not hasattr(first, "functions")
    assert not hasattr(first, "_bind_resources")

    serialized = document.model_dump()
    assert serialized["profiles"]["first"]["grain"] == [{"dimension": "key", "resolution": "key"}]
    assert "functions" not in serialized["profiles"]["first"]
    restored = model.Spec.model_validate(serialized)
    assert restored.model_dump() == serialized


def test_new_model_discovers_edits_without_invalidation_machinery() -> None:
    document = _sample_spec()
    previous = document.features
    assert document.arguments
    document.profiles["first"].features["new"] = model.Feature(id="new")
    document.functions["load"].args["extra"] = model.Argument(id="extra", type="str")
    assert "new" not in previous
    assert ("load", "extra") not in document.arguments
    reconstructed = model.Spec.model_validate(document.model_dump())
    assert reconstructed.features["new"] is reconstructed.profiles["first"].features["new"]
    assert ("load", "extra") in reconstructed.arguments

    reconstructed = _sample_spec()
    reconstructed.profiles["wrong"] = model.Profile(id="different")
    with pytest.raises(ValueError, match="Profile key wrong does not match profile id different"):
        validation.validate_spec(reconstructed)


def test_indexes_preserve_action_aliases_and_diagnostic_paths() -> None:
    document = _sample_spec()
    action = document.profiles["first"].actions["read"]
    document.profiles["first"].actions["alias"] = action
    action.binding.function = "missing"
    key = ("first", "alias")
    assert document.actions_by_key[key] is action
    assert document.action_profiles[key] is document.profiles_by_key["first"]
    assert document.actions[:2] == [action, action]
    assert document.action_paths[key][-1] == "read"
    assert document.declaration_paths[key][-1] == "alias"
    assert action.binding.function not in document.functions


def test_nested_models_expose_cached_children_and_normalized_ids() -> None:
    document = _sample_spec()
    profile = document.profiles["first"]
    profile.grain = _CountingList(profile.grain)
    action = profile.actions["read"]
    action.features.inputs = _CountingList(["$features.another"])
    action.features.outputs = _CountingList(action.features.outputs)
    profile.order = _CountingList(
        [
            model.Order(dimension="key", resolution="key", direction="asc"),
            model.Order(dimension="key", resolution="key", direction="desc"),
        ]
    )
    document.functions["load"].args = _CountingDict(document.functions["load"].args)
    assert document.arguments
    for _ in range(3):
        assert profile.dimension_ids == ["key"]
        assert profile.dimension_id_set == frozenset({"key"})
        assert profile.features["value"].id == "value"
        assert profile.actions["read"] is action
        assert profile.arguments["read", "path"] == "first"
        assert action.arguments is action.binding.args
        assert profile.feature_producers["value"] == (("read", action),)
        assert action.input_features is action.features.input_ids
        assert action.input_features == ["another"]
        assert action.output_features is action.features.output_ids
        assert action.output_features == ["key", "value"]
        assert profile.order_dimensions == (("key", frozenset()), ("key", frozenset({"key"})))
        assert profile.order_references == frozenset({"$dimensions.key"})
        assert action.dataset_references == ()
        assert action.feature_selectors == ()
        assert action.dimensions_references == ()
    assert profile.grain.traversals == 1
    assert action.features.inputs.traversals == 1
    assert action.features.outputs.traversals == 1
    assert profile.order.traversals == 1
    assert document.functions["load"].args.traversals == 1


class _CountingList(list[typing.Any]):
    traversals = 0

    def __iter__(self) -> collections.abc.Iterator[typing.Any]:
        self.traversals += 1
        return super().__iter__()
