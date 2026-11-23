import polars as pl
import pytest

from uptimely.engine.dataframe import backend
from uptimely.spec import feature_types


@pytest.mark.parametrize("lazy", [False, True])
def test_backend_value_queries(lazy: bool) -> None:
    adapter = backend.PolarsBackend()
    frame = pl.DataFrame({"key": ["A"]})
    value = frame.lazy() if lazy else frame

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
        assert isinstance(snapshot, pl.DataFrame)
        frame.replace_column(0, pl.Series("value", [3, 4]))
        assert snapshot["value"].to_list() == [1, 2]
