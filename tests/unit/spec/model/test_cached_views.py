import collections.abc
import typing

import pytest

from uptimely.spec import model, validation
from uptimely.spec.validation.rules import bindings


def _sample_spec() -> model.Spec:
    return model.Spec.model_validate(
        {
            "dimensions": {"key": {"resolutions": {"key": {"key": "key", "type": "integer"}}}},
            "functions": {
                name: {
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
                    "assembly": {
                        "read": {
                            "compute": {"function": function, "args": {"path": profile}},
                            "interface": {"outputs": ["$features.key", f"$features.{feature}"]},
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


def test_structural_types_include_only_grain_keys_and_declared_relations() -> None:
    payload = _sample_spec().model_dump()
    payload["dimensions"] = {
        "key": {
            "resolutions": {
                "key": {"key": "key", "type": "integer", "parent": "parent"},
                "parent": {"key": "parent_id", "type": "string"},
                "sibling": {"key": "sibling_id", "type": "string", "parent": "parent"},
                "child": {"key": "child_id", "type": "integer", "parent": "key"},
            }
        },
        "unused": {"resolutions": {"other": {"key": "other_id", "type": "string"}}},
    }
    document = model.Spec.model_validate(payload)

    assert document.key_types_by_profile == {
        profile: {"key": "integer"} for profile in ("first", "second")
    }
    assert document.relation_types_by_profile == {"first": {}, "second": {}}
    for profile in payload["profiles"].values():
        profile["relations"] = [{"dimension": "key", "resolution": "parent"}]
    document = model.Spec.model_validate(payload)
    assert document.key_types_by_profile == {
        profile: {
            "key": "integer",
            "parent_id": "string",
        }
        for profile in ("first", "second")
    }
    assert document.identifiers_by_profile == {"first": ["key"], "second": ["key"]}
    for profile_id, profile in document.profiles.items():
        assert (
            profile.identifier_types(document.dimensions)
            == document.identifier_types_by_profile[profile_id]
        )
        assert profile.identifiers(document.dimensions) == ["key"]
        assert profile.keys(document.dimensions) == ["key", "parent_id"]
        assert profile.key_types(document.dimensions) == {"key": "integer", "parent_id": "string"}
        assert profile.relation_types(document.dimensions) == {"parent_id": "string"}
        assert document.relation_types_by_profile[profile_id] == {"parent_id": "string"}


def test_dimensionless_profile_exposes_no_identifiers() -> None:
    profile = model.Profile(id="global")

    assert profile.keys({}) == []
    assert profile.key_types({}) == {}


def test_cached_views_build_only_the_views_they_need() -> None:
    document = _sample_spec()
    counted = []
    document.profiles = _CountingDict(document.profiles)
    counted.append(document.profiles)
    for profile in document.profiles.values():
        profile.features = _CountingDict(profile.features)
        profile.assembly = _CountingDict(profile.assembly)
        counted.extend([profile.features, profile.assembly])
    for function in document.functions.root.values():
        function.args = _CountingDict(function.args)
        counted.append(function.args)
    for collection in counted:
        collection.traversals = 0

    assert list(document.profiles_by_key) == ["first", "second"]
    assert document.profiles_by_key is document.profiles_by_key
    assert all(profile.features.traversals == 0 for profile in document.profiles.values())
    assert all(profile.assembly.traversals == 0 for profile in document.profiles.values())

    assert list(document.features) == ["key", "value", "another"]
    assert document.features is document.features
    assert all(profile.features.traversals == 1 for profile in document.profiles.values())
    assert all(profile.assembly.traversals == 0 for profile in document.profiles.values())

    assert list(document.operators_by_key) == [("first", "read"), ("second", "read")]
    assert document.operators_by_key is document.operators_by_key
    assert all(profile.assembly.traversals == 1 for profile in document.profiles.values())
    assert document.operator_profiles == {
        ("first", "read"): document.profiles_by_key["first"],
        ("second", "read"): document.profiles_by_key["second"],
    }
    assert list(document.arguments) == [
        ("load", "path"),
        ("other", "path"),
    ]
    assert document.identifiers_by_profile == {"first": ["key"], "second": ["key"]}
    assert len(document.operators) == 2
    assert len(document.profile_items) == 2
    assert document.operators_by_function["load"] == [("first", "read")]
    assert document.feature_producers["value"] == [("first", "read")]
    assert document.operators[0] is document.profiles["first"].assembly["read"]
    assert document.features["value"] is document.profiles["first"].features["value"]

    assert document.profiles.traversals > 0
    assert all(profile.features.traversals == 1 for profile in document.profiles.values())
    assert all(profile.assembly.traversals == 1 for profile in document.profiles.values())
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


def test_rebuild_discovers_edits_after_cached_views_are_warmed() -> None:
    document = _sample_spec()
    previous = document.features
    assert document.arguments
    document.profiles["first"].features["new"] = model.Feature(id="new")
    document.functions["load"].args["extra"] = model.Argument(id="extra", type="str")
    assert "new" not in previous
    assert ("load", "extra") not in document.arguments
    reconstructed = document.rebuild()
    assert reconstructed is not document
    assert reconstructed.features["new"] is reconstructed.profiles["first"].features["new"]
    assert ("load", "extra") in reconstructed.arguments

    reconstructed = _sample_spec()
    reconstructed.profiles["wrong"] = model.Profile(id="different")
    with pytest.raises(ValueError, match="Profile key wrong does not match profile id different"):
        validation.validate_spec(reconstructed)


def test_cached_views_preserve_operator_aliases_and_diagnostic_paths() -> None:
    document = _sample_spec()
    operator = document.profiles["first"].assembly["read"]
    document.profiles["first"].assembly["alias"] = operator
    operator.compute.function = "missing"
    key = ("first", "alias")
    assert document.operators_by_key[key] is operator
    assert document.operator_profiles[key] is document.profiles_by_key["first"]
    assert document.operators[:2] == [operator, operator]
    assert document.operator_paths[key][-1] == "alias"
    assert document.declaration_paths[key][-1] == "alias"
    assert operator.compute.function not in document.functions


def test_operator_bindings_preserve_identity_aliases_order_and_unresolved_functions() -> None:
    document = _sample_spec()
    profile = document.profiles["first"]
    operator = profile.assembly["read"]
    operator.merge = model.Binding(function="missing", args={"dataset": "$profiles.@.dataset"})
    profile.assembly["alias"] = operator
    original = document.model_dump()
    assert list(operator.bindings) == ["compute", "merge"]
    assert operator.bindings["compute"] is operator.compute
    alias = document.operators_by_key["first", "alias"]
    assert alias is operator
    assert alias.bindings["compute"] is operator.compute
    assert alias.bindings["merge"] is operator.merge
    assert document.functions.root.get(operator.merge.function) is None
    assert document.profiles["second"].assembly["read"].bindings == {
        "compute": document.profiles["second"].assembly["read"].compute,
    }
    assert document.model_dump() == original
    assert document.binding_selectors_with_paths == tuple(
        (path, leaf.root, kind) for path, leaf, kind in document.binding_arguments_with_paths
    )
    assert [path for path, _, _ in document.binding_arguments_with_paths] == [
        ("profiles", "first", "assembly", "read", "compute", "args"),
        ("profiles", "first", "assembly", "alias", "compute", "args"),
        ("profiles", "second", "assembly", "read", "compute", "args"),
    ]
    assert document.binding_arguments_with_paths is document.binding_arguments_with_paths


@pytest.mark.parametrize("binding_name", ["compute", "merge"])
def test_argument_mismatch_shortcut_preserves_sorted_details_and_alias_path(
    binding_name: str,
) -> None:
    document = _sample_spec()
    profile = document.profiles["first"]
    operator = profile.assembly.pop("read")
    profile.assembly["alias"] = operator
    invalid = model.Binding(function="load", args={"z": None, "a": None})
    setattr(operator, binding_name, invalid)
    with pytest.raises(validation.SpecError) as error:
        bindings.validate_arguments(document)
    assert error.value.code == "invalid_binding_arguments"
    assert str(error.value) == (
        f"profiles.first.assembly.alias.{binding_name}.args: "
        "Binding for function load has missing arguments: path; unknown arguments: a, z"
    )
    assert error.value.path == ("profiles", "first", "assembly", "alias", binding_name, "args")


def test_metadata_shortcut_does_not_skip_unknown_functions() -> None:
    document = _sample_spec()
    operator = document.profiles["first"].assembly["read"]
    operator.compute = model.Binding(
        function="missing", args={"nested": ["$dimensions.missing.name"]}
    )
    assert document.functions.root.get(operator.compute.function) is None
    with pytest.raises(validation.SpecError) as error:
        bindings.validate_selector_metadata(document)
    assert error.value.code == "invalid_binding_selector"
    assert error.value.path == (
        "profiles",
        "first",
        "assembly",
        "read",
        "compute",
        "args",
        "nested",
        0,
    )


def test_nested_models_expose_cached_children_and_normalized_ids() -> None:
    document = _sample_spec()
    profile = document.profiles["first"]
    profile.grain = _CountingList(profile.grain)
    operator = profile.assembly["read"]
    operator.interface.inputs = _CountingList(["$features.another"])
    operator.interface.outputs = _CountingList(operator.interface.outputs)
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
        assert profile.assembly["read"] is operator
        assert profile.arguments["read", "path"].root == "first"
        assert operator.arguments is operator.compute.args
        assert profile.feature_producers["value"] == (("read", operator),)
        assert operator.input_features is operator.interface.input_ids
        assert operator.input_features == ["another"]
        assert operator.output_features is operator.interface.output_ids
        assert operator.output_features == ["key", "value"]
        assert profile.order_dimensions == (("key", frozenset()), ("key", frozenset({"key"})))
        assert profile.order_references == frozenset({"$dimensions.key"})
        assert operator.profile_references == ()
        assert operator.feature_selectors == ()
        assert operator.dimensions_references == ()
    assert profile.grain.traversals == 1
    assert operator.interface.inputs.traversals == 1
    assert operator.interface.outputs.traversals == 1
    assert profile.order.traversals == 1
    assert document.functions["load"].args.traversals == 1


class _CountingList(list[typing.Any]):
    traversals = 0

    def __iter__(self) -> collections.abc.Iterator[typing.Any]:
        self.traversals += 1
        return super().__iter__()
