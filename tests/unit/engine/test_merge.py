"""Merge ownership, identifier handling, and publication boundaries."""

import polars as pl
import pytest

from uptimely import engine


@pytest.mark.parametrize("lazy", [False, True])
def test_merge_uses_fragment_keys_without_invocation_metadata(lazy: bool) -> None:
    target = pl.DataFrame({"pump": ["p1", "p2"], "series": ["s1", "s1"]})
    contribution = pl.DataFrame({"series": ["s1"], "capacity": [90.0]})
    if lazy:
        target, contribution = target.lazy(), contribution.lazy()
    dataset = engine.Dataset(engine.PolarsBackend(), ["pump"], target)
    fragment = engine.Fragment(contribution, ("series",))

    result = engine.Merge(dataset, fragment).execute(validate=True)

    assert fragment.invocation is None
    assert fragment.identifiers == ("series",)
    assert dataset.dataframe is target
    assert dataset.fragments == {}
    if lazy:
        result = result.collect()
    assert result.to_dicts() == [
        {"pump": "p1", "series": "s1", "capacity": 90.0},
        {"pump": "p2", "series": "s1", "capacity": 90.0},
    ]


def test_full_grain_merge_coalesces_explicit_fragment_keys() -> None:
    dataset = engine.Dataset(
        engine.PolarsBackend(),
        ["pump"],
        pl.DataFrame({"pump": ["p1"], "series": [None]}, schema_overrides={"series": pl.String}),
    )
    fragment = engine.Fragment(
        pl.DataFrame({"pump": ["p1"], "series": ["s1"], "capacity": [90.0]}),
        ("pump",),
        relations=("series",),
    )

    result = engine.Merge(dataset, fragment).execute(validate=True)

    assert fragment.identifiers == ("pump",)
    assert fragment.relations == ("series",)
    assert fragment.keys == ("pump", "series")
    assert result.to_dicts() == [{"pump": "p1", "series": "s1", "capacity": 90.0}]


def test_identifier_and_relation_roles_are_relative_to_each_frame() -> None:
    dataset = engine.Dataset(
        engine.PolarsBackend(),
        ["pump"],
        pl.DataFrame({"pump": ["p1", "p2"], "series": ["s1", "s1"]}),
        relations=["series"],
    )
    fragment = engine.Fragment(
        pl.DataFrame({"series": ["s1"], "capacity": [90.0]}),
        ("series",),
    )

    assert dataset.identifiers == ("pump",)
    assert dataset.relations == ("series",)
    assert dataset.keys == ("pump", "series")
    assert fragment.identifiers == ("series",)
    assert fragment.relations == ()
    assert fragment.keys == ("series",)
    dataset.merge(fragment)
    assert dataset.identifiers == ("pump",)
    assert dataset.relations == ("series",)
    assert dataset.dataframe["capacity"].to_list() == [90.0, 90.0]


def test_dataset_retains_relations_from_full_grain_fragments() -> None:
    dataset = engine.Dataset(engine.PolarsBackend(), ["pump"])
    fragment = engine.Fragment(
        pl.DataFrame({"pump": ["p1"], "series": ["s1"], "value": [1]}),
        ("pump",),
        relations=("series",),
    )
    dataset.merge(fragment)
    assert dataset.identifiers == fragment.identifiers == ("pump",)
    assert dataset.relations == fragment.relations == ("series",)
    assert dataset.keys == fragment.keys == ("pump", "series")


@pytest.mark.parametrize("invalid", [False, True])
def test_merge_invokes_custom_assembly_once_without_publishing(invalid: bool) -> None:
    target = pl.DataFrame({"key": ["a"], "old": [1]})
    dataset = engine.Dataset(engine.PolarsBackend(), ["key"], target)
    fragment = engine.Fragment(pl.DataFrame({"key": ["a"], "new": [2]}), ("key",))
    calls = []

    def assemble() -> pl.DataFrame:
        calls.append("custom")
        return target if invalid else target.with_columns(pl.lit(42).alias("new"))

    operation = engine.Merge(dataset, fragment)
    if invalid:
        with pytest.raises(ValueError, match="missing required columns: new"):
            operation.execute(assemble)
    else:
        assert operation.execute(assemble)["new"].to_list() == [42]
    assert calls == ["custom"]
    assert dataset.dataframe is target
    assert dataset.fragments == {}


def test_collision_is_rejected_before_custom_assembly() -> None:
    target = pl.DataFrame({"key": ["a"], "value": [1]})
    dataset = engine.Dataset(engine.PolarsBackend(), ["key"], target)
    fragment = engine.Fragment(target, ("key",))

    def assemble() -> object:
        pytest.fail("A colliding fragment must fail before invoking the merge function")

    with pytest.raises(ValueError, match="overlap.*value"):
        engine.Merge(dataset, fragment).execute(assemble)
    assert dataset.dataframe is target


def test_custom_merge_failure_propagates_without_fallback() -> None:
    dataset = engine.Dataset(engine.PolarsBackend(), ["key"])
    fragment = engine.Fragment(pl.DataFrame({"key": ["a"], "value": [1]}), ("key",))

    def assemble() -> object:
        raise RuntimeError("custom merge failed")

    with pytest.raises(RuntimeError, match="custom merge failed"):
        engine.Merge(dataset, fragment).execute(assemble)
    assert dataset.dataframe is None
    assert dataset.fragments == {}
