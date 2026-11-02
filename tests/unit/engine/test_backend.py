import polars as pl
import pytest

from uptimely.engine.dataframe import backend


@pytest.mark.parametrize("keys", [[], ["key"]])
@pytest.mark.parametrize("operation", ["join", "left_join"])
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


@pytest.mark.parametrize("lazy", [False, True])
@pytest.mark.parametrize("operation", ["join", "left_join"])
def test_join_validation_is_explicit(lazy: bool, operation: str) -> None:
    adapter = backend.PolarsBackend()
    left = pl.DataFrame({"left": [1, 2]})
    right = pl.DataFrame({"right": [3, 4]})
    if lazy:
        left, right = left.lazy(), right.lazy()

    with pytest.raises(ValueError, match="at most one global row"):
        getattr(adapter, operation)(left, right, [])

    result = getattr(adapter, operation)(left, right, [], validate="m:m")
    if lazy:
        result = result.collect()
    assert result.height == 4
