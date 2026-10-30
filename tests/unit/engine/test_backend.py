import polars as pl
import pytest

from uptimely.engine.dataframe import backend


@pytest.mark.parametrize("keys", [[], ["key"]])
def test_disabled_lazy_validation_does_not_execute_join(
    monkeypatch: pytest.MonkeyPatch, keys: list[str]
) -> None:
    left = pl.DataFrame({"key": ["A"], "left": [1]}).lazy()
    right = pl.DataFrame({"key": ["A"], "right": [2]}).lazy()
    if not keys:
        right = right.drop("key")

    def unexpected_collect(*args: object, **kwargs: object) -> None:
        pytest.fail("Lazy query executed during join construction")

    monkeypatch.setattr(pl.LazyFrame, "collect", unexpected_collect)
    adapter = backend.PolarsBackend(validate_lazy_frames=False)

    assert not adapter.should_validate_values(left)
    assert isinstance(adapter.join(left, right, keys), pl.LazyFrame)


@pytest.mark.parametrize("operation", ["row_count", "is_duplicated", "same_keys"])
def test_disabled_lazy_value_queries_fail_explicitly(
    monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    adapter = backend.PolarsBackend(validate_lazy_frames=False)
    frame = pl.DataFrame({"key": ["A"]}).lazy()

    def unexpected_collect(*args: object, **kwargs: object) -> None:
        pytest.fail("Disabled lazy query executed")

    monkeypatch.setattr(pl.LazyFrame, "collect", unexpected_collect)
    with pytest.raises(ValueError, match="Implicit lazy execution is disabled"):
        if operation == "same_keys":
            adapter.same_keys(frame, frame, ["key"])
        else:
            getattr(adapter, operation)(frame)


def test_disabled_lazy_validation_allows_explicit_collection() -> None:
    adapter = backend.PolarsBackend(validate_lazy_frames=False)
    frame = pl.DataFrame({"key": ["A"]})

    assert adapter.collect(frame.lazy()).equals(frame)
    assert adapter.should_validate_values(frame)
    assert adapter.row_count(frame) == 1
    assert not adapter.is_duplicated(frame)
    assert adapter.same_keys(frame, frame, ["key"])


def test_disabled_lazy_validation_retains_deferred_join_validation() -> None:
    adapter = backend.PolarsBackend(validate_lazy_frames=False)
    left = pl.DataFrame({"left": [1, 2]}).lazy()
    right = pl.DataFrame({"right": [3]}).lazy()

    joined = adapter.join(left, right, [])

    with pytest.raises(pl.exceptions.ComputeError, match="1:1"):
        adapter.collect(joined)


def test_disabled_lazy_validation_still_validates_eager_dimensionless_rows() -> None:
    adapter = backend.PolarsBackend(validate_lazy_frames=False)
    left = pl.DataFrame({"left": [1, 2]})
    right = pl.DataFrame({"right": [3]}).lazy()

    with pytest.raises(ValueError, match="at most one global row"):
        adapter.join(left, right, [])
