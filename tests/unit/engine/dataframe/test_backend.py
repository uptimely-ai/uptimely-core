import polars as pl
import pytest

from uptimely.engine.dataframe import backend
from uptimely.spec import feature_types


@pytest.mark.parametrize(
    ("keys", "operation"), [([], "join"), (["key"], "join"), (["key"], "left_join")]
)
def test_unvalidated_lazy_join_does_not_execute(
    monkeypatch: pytest.MonkeyPatch, keys: list[str], operation: str
) -> None:
    left = pl.DataFrame({"key": ["A"], "left": [1]}).lazy()
    right = pl.DataFrame({"key": ["A"], "right": [2]}).lazy()
    if not keys:
        right = right.drop("key")

    def unexpected_collect(*args: object, **kwargs: object) -> None:
        pytest.fail("Lazy query executed during join construction")

    monkeypatch.setattr(pl.LazyFrame, "collect", unexpected_collect)
    adapter = backend.PolarsBackend()
    joined = getattr(adapter, operation)(left, right, keys, validate="m:m")

    assert isinstance(joined, pl.LazyFrame)


@pytest.mark.parametrize("lazy", [False, True])
def test_backend_value_queries(lazy: bool) -> None:
    adapter = backend.PolarsBackend()
    frame = pl.DataFrame({"key": ["A"]})
    value = frame.lazy() if lazy else frame

    assert adapter.collect(frame.lazy()).equals(frame)
    assert adapter.row_count(value) == 1
    assert not adapter.is_duplicated(value)
    assert adapter.same_keys(value, value, ["key"])
    assert adapter.same_data(value, value, ["key"])


def test_backend_reports_supported_feature_types() -> None:
    with pytest.raises(ValueError) as error:
        backend.PolarsBackend().validate_types(pl.DataFrame({"value": [1]}), {"value": "floatti"})

    assert str(error.value) == (
        "Unsupported feature type for value: floatti. "
        f"Supported types: {', '.join(feature_types.FEATURE_TYPES)}"
    )


@pytest.mark.parametrize("lazy", [False, True])
def test_backend_same_data_preserves_row_order_and_values(lazy: bool) -> None:
    adapter = backend.PolarsBackend()
    original = pl.DataFrame({"key": ["A", "B"], "value": [1, 2]})
    reordered = original.reverse()
    if lazy:
        original, reordered = original.lazy(), reordered.lazy()

    assert not adapter.same_data(original, reordered, ["key", "value"])


@pytest.mark.parametrize("lazy", [False, True])
def test_backend_snapshot_preserves_dataframe_interface(lazy: bool) -> None:
    adapter = backend.PolarsBackend()
    frame = pl.DataFrame({"value": [1, 2]})
    snapshot = adapter.snapshot(frame.lazy() if lazy else frame)

    if lazy:
        assert isinstance(snapshot, pl.LazyFrame)
        assert snapshot.collect().equals(frame)
    else:
        assert snapshot is frame


@pytest.mark.parametrize("lazy", [False, True])
@pytest.mark.parametrize("operation", ["join", "left_join"])
def test_join_validation_is_explicit(lazy: bool, operation: str) -> None:
    adapter = backend.PolarsBackend()
    left = pl.DataFrame({"left": [1, 2]})
    right = pl.DataFrame({"right": [3, 4]})
    if lazy:
        left, right = left.lazy(), right.lazy()

    keys = ["key"] if operation == "left_join" else []
    if keys:
        left = left.with_columns(pl.lit(0).alias("key"))
        right = right.with_columns(pl.lit(0).alias("key"))
    cardinality = "m:1" if operation == "left_join" else "1:1"
    with pytest.raises(pl.exceptions.ComputeError, match=cardinality):
        joined = getattr(adapter, operation)(left, right, keys)
        if lazy:
            joined.collect()

    result = getattr(adapter, operation)(left, right, keys, validate="m:m")
    if lazy:
        result = result.collect()
    assert result.height == 4


@pytest.mark.parametrize("lazy", [False, True])
@pytest.mark.parametrize(("left_rows", "right_rows"), [(0, 0), (0, 2), (2, 0), (2, 3)])
def test_cross_join_is_a_generic_cartesian_product(
    lazy: bool, left_rows: int, right_rows: int
) -> None:
    left = pl.DataFrame({"left": list(range(left_rows))})
    right = pl.DataFrame({"right": list(range(right_rows))})
    if lazy:
        left, right = left.lazy(), right.lazy()

    result = backend.PolarsBackend().cross_join(left, right)
    if lazy:
        result = result.collect()

    assert result.height == left_rows * right_rows
