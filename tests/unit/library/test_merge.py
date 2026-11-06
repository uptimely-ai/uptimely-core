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


def test_merge_by_grain_rejects_incompatible_fragment_keys() -> None:
    target = pl.DataFrame({"id": [1]})
    fragment = pl.DataFrame({"other": [1]})

    with pytest.raises(ValueError, match="must be a subset"):
        merge.merge_by_grain(target, fragment, ["id"], ["other"])
