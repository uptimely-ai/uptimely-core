import polars as pl
import pytest

from uptimely.library.merge import polars as merge


@pytest.mark.parametrize("lazy", [False, True])
def test_merge_by_grain_full_join_matches_null_keys(lazy: bool) -> None:
    target = pl.DataFrame({"id": [None, 1], "value": [10, 20]})
    fragment = pl.DataFrame({"id": [None, 2], "new": [100, 200]})
    if lazy:
        target, fragment = target.lazy(), fragment.lazy()

    result = merge.merge_by_grain(target, fragment, ["id"], ["id"])
    if lazy:
        result = result.collect()

    assert result.sort("id", nulls_last=True).to_dicts() == [
        {"id": 1, "value": 20, "new": None},
        {"id": 2, "value": None, "new": 200},
        {"id": None, "value": 10, "new": 100},
    ]


@pytest.mark.parametrize(
    ("fragment_keys", "fragment", "expected"),
    [
        (
            ["group"],
            pl.DataFrame({"group": ["A"], "new": [3]}),
            [
                {"group": "A", "id": 1, "value": 10, "new": 3},
                {"group": "A", "id": 2, "value": 20, "new": 3},
            ],
        ),
        (
            [],
            pl.DataFrame({"new": [3]}),
            [
                {"group": "A", "id": 1, "value": 10, "new": 3},
                {"group": "A", "id": 2, "value": 20, "new": 3},
            ],
        ),
    ],
)
def test_merge_by_grain_broadcasts_subset_and_dimensionless_fragments(
    fragment_keys: list[str], fragment: pl.DataFrame, expected: list[dict[str, object]]
) -> None:
    target = pl.DataFrame({"group": ["A", "A"], "id": [1, 2], "value": [10, 20]})

    result = merge.merge_by_grain(target, fragment, ["group", "id"], fragment_keys)

    assert result.sort("id").to_dicts() == expected


def test_merge_by_grain_full_join_without_keys_uses_collision_safe_internal_key() -> None:
    target = pl.DataFrame({"__join_key": [1], "left": ["target"]})
    fragment = pl.DataFrame({"__join_key": [2], "right": ["fragment"]})

    result = merge.merge_by_grain(target, fragment, [], [])

    assert result.to_dicts() == [
        {"__join_key": 1, "left": "target", "__join_key_right": 2, "right": "fragment"}
    ]
    assert "__join_key_" not in result.columns


def test_merge_by_grain_initializes_only_from_complete_grain() -> None:
    fragment = pl.DataFrame({"id": [1], "value": [2]})

    assert merge.merge_by_grain(None, fragment, ["id"], ["id"]) is fragment
    with pytest.raises(ValueError, match="requires the accumulated"):
        merge.merge_by_grain(None, fragment, ["id", "group"], ["id"])


def test_merge_by_grain_infers_carried_keys_from_fragment_schema() -> None:
    target = pl.DataFrame({"group": ["A", "A"], "id": [1, 2], "value": [10, 20]})
    fragment = pl.DataFrame({"group": ["A"], "new": [3]})

    result = merge.merge_by_grain(target, fragment, ["group", "id"])

    assert result.sort("id").to_dicts() == [
        {"group": "A", "id": 1, "value": 10, "new": 3},
        {"group": "A", "id": 2, "value": 20, "new": 3},
    ]


def test_merge_by_grain_rejects_incompatible_fragment_keys() -> None:
    target = pl.DataFrame({"id": [1]})
    fragment = pl.DataFrame({"other": [1]})

    with pytest.raises(ValueError, match="must be a subset"):
        merge.merge_by_grain(target, fragment, ["id"], ["other"])


@pytest.mark.parametrize("lazy", [False, True])
def test_merge_by_grain_matches_parent_keys_without_expanding_target_scope(lazy: bool) -> None:
    target = pl.DataFrame(
        {"pump": ["p1", "p2", "p3", "p4"], "series": ["s1", "s1", "missing", None]}
    )
    fragment = pl.DataFrame({"series": ["s1", "unused", None], "capacity": [90.0, 100.0, 80.0]})
    if lazy:
        target, fragment = target.lazy(), fragment.lazy()

    result = merge.merge_by_grain(
        target, fragment, ["pump"], key_columns=["series"], broadcast_cardinality="m:1"
    )
    if lazy:
        result = result.collect()

    assert result.sort("pump").to_dicts() == [
        {"pump": "p1", "series": "s1", "capacity": 90.0},
        {"pump": "p2", "series": "s1", "capacity": 90.0},
        {"pump": "p3", "series": "missing", "capacity": None},
        {"pump": "p4", "series": None, "capacity": 80.0},
    ]


def test_parent_merge_uses_all_matching_identifiers() -> None:
    target = pl.DataFrame({"pump": ["p1", "p2"], "plant": ["A", "B"], "series": ["s1", "s1"]})
    fragment = pl.DataFrame({"plant": ["A", "B"], "series": ["s1", "s1"], "capacity": [90.0, 80.0]})

    result = merge.merge_by_grain(
        target, fragment, ["pump", "plant"], key_columns=["plant", "series"]
    )

    assert result["capacity"].to_list() == [90.0, 80.0]


def test_parent_merge_requires_a_dataset_with_matching_keys() -> None:
    fragment = pl.DataFrame({"series": ["s1"], "capacity": [90.0]})

    with pytest.raises(ValueError, match="requires the accumulated"):
        merge.merge_by_grain(None, fragment, ["pump"], key_columns=["series"])
    with pytest.raises(ValueError, match="Matching keys are missing from the dataset: series"):
        merge.merge_by_grain(
            pl.DataFrame({"pump": ["p1"]}), fragment, ["pump"], key_columns=["series"]
        )


def test_parent_merge_rejects_duplicate_source_identifiers_when_cardinality_is_checked() -> None:
    with pytest.raises(pl.exceptions.ComputeError, match="m:1"):
        merge.merge_by_grain(
            pl.DataFrame({"pump": ["p1"], "series": ["s1"]}),
            pl.DataFrame({"series": ["s1", "s1"], "capacity": [90.0, 80.0]}),
            ["pump"],
            key_columns=["series"],
            broadcast_cardinality="m:1",
        )


@pytest.mark.parametrize("lazy", [False, True])
def test_full_grain_merge_coalesces_other_resolution_keys(lazy: bool) -> None:
    target = pl.DataFrame({"pump": ["p1", "p2"], "series": ["s1", None], "value": [10, 20]})
    fragment = pl.DataFrame(
        {
            "pump": ["p2", "p3"],
            "series": ["s2", "s3"],
            "category": ["c1", "c2"],
            "new": [30, 40],
            "series__identifier": [50, 60],
        }
    )
    if lazy:
        target, fragment = target.lazy(), fragment.lazy()

    result = merge.merge_by_grain(
        target,
        fragment,
        ["pump"],
        key_columns=["pump", "series", "category"],
        join_cardinality="1:1",
    )
    if lazy:
        result = result.collect()

    assert result.sort("pump").to_dicts() == [
        {
            "pump": "p1",
            "series": "s1",
            "value": 10,
            "category": None,
            "new": None,
            "series__identifier": None,
        },
        {
            "pump": "p2",
            "series": "s2",
            "value": 20,
            "category": "c1",
            "new": 30,
            "series__identifier": 50,
        },
        {
            "pump": "p3",
            "series": "s3",
            "value": None,
            "category": "c2",
            "new": 40,
            "series__identifier": 60,
        },
    ]
