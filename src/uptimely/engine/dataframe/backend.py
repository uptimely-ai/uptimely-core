"""Backend and runtime protocols used by the execution engine."""

from __future__ import annotations

import typing
from collections import abc

import polars as pl

from uptimely.library.merge import polars as merge_module
from uptimely.spec import feature_types

from .. import config as config_module


class DataFrameBackend(typing.Protocol):
    """Operations required by the engine from a dataframe backend."""

    name: str

    def is_frame(self, value: object) -> bool: ...

    def column_names(self, frame: object) -> list[str]: ...

    def select(self, frame: object, columns: abc.Sequence[str]) -> object: ...

    def lazy(self, frame: object) -> object: ...

    def join(
        self, left: object, right: object, keys: abc.Sequence[str], *, validate: str = "1:1"
    ) -> object: ...

    def left_join(
        self, left: object, right: object, keys: abc.Sequence[str], *, validate: str = "m:1"
    ) -> object: ...

    def cross_join(self, left: object, right: object) -> object: ...

    def collect(self, frame: object) -> object: ...

    def snapshot(self, frame: object) -> object: ...

    def is_duplicated(self, frame: object) -> bool: ...

    def row_count(self, frame: object) -> int: ...

    def same_keys(self, left: object, right: object, keys: abc.Sequence[str]) -> bool: ...

    def same_data(self, left: object, right: object, columns: abc.Sequence[str]) -> bool: ...

    def validate_types(self, frame: object, types: abc.Mapping[str, str]) -> None: ...


class PolarsBackend:
    """Polars implementation of the engine dataframe contract."""

    name = "polars"

    def is_frame(self, value: object) -> bool:
        return isinstance(value, (pl.DataFrame, pl.LazyFrame))

    def column_names(self, frame: object) -> list[str]:
        if isinstance(frame, pl.LazyFrame):
            return frame.collect_schema().names()
        return list(frame.columns)

    def select(self, frame: object, columns: abc.Sequence[str]) -> object:
        return frame.select(*columns)

    def lazy(self, frame: object) -> object:
        return frame.lazy()

    def join(
        self, left: object, right: object, keys: abc.Sequence[str], *, validate: str = "1:1"
    ) -> object:
        """Full-join dataframes using the shared Polars merge implementation."""
        return merge_module.full_join(left, right, keys, validate=validate)

    def left_join(
        self, left: object, right: object, keys: abc.Sequence[str], *, validate: str = "m:1"
    ) -> object:
        """Left-join dataframes using the shared Polars merge implementation."""
        return merge_module.left_join(left, right, keys, validate=validate)

    def cross_join(self, left: object, right: object) -> object:
        """Return the Cartesian product using the shared Polars merge implementation."""
        return merge_module.cross_join(left, right)

    def collect(self, frame: object) -> object:
        return frame.collect()

    def snapshot(self, frame: object) -> object:
        """Materialize lazy input once while preserving its lazy dataframe interface."""
        if isinstance(frame, pl.LazyFrame):
            return frame.collect().lazy()
        return frame

    def is_duplicated(self, frame: object) -> bool:
        if isinstance(frame, pl.LazyFrame):
            frame = frame.collect()
        return bool(frame.is_duplicated().any())

    def row_count(self, frame: object) -> int:
        """Return the row count without materializing all columns of a lazy frame."""
        count = frame.select(pl.len())
        if isinstance(count, pl.LazyFrame):
            count = count.collect()
        return count.item()

    def same_keys(self, left: object, right: object, keys: abc.Sequence[str]) -> bool:
        """Compare observation identities without assuming physical row order."""
        if not keys:
            return self.row_count(left) == self.row_count(right)
        left_keys = left.select(list(keys))
        right_keys = right.select(list(keys))
        if isinstance(left_keys, pl.LazyFrame):
            left_keys = left_keys.collect()
        if isinstance(right_keys, pl.LazyFrame):
            right_keys = right_keys.collect()
        return left_keys.sort(list(keys)).equals(right_keys.sort(list(keys)))

    def same_data(self, left: object, right: object, columns: abc.Sequence[str]) -> bool:
        """Compare selected rows and values in order, collecting lazy frames if needed."""
        left_data = self.select(left, columns)
        right_data = self.select(right, columns)
        if isinstance(left_data, pl.LazyFrame):
            left_data = left_data.collect()
        if isinstance(right_data, pl.LazyFrame):
            right_data = right_data.collect()
        return left_data.equals(right_data)

    def validate_types(self, frame: object, types: abc.Mapping[str, str]) -> None:
        """Check declared logical column types against the returned schema."""
        schema = frame.collect_schema()
        for name, expected in types.items():
            actual = schema[name]
            compatible = {
                feature_types.STRING: actual == pl.String,
                feature_types.INTEGER: actual.is_integer(),
                feature_types.FLOAT: actual.is_float(),
                feature_types.NUMERIC: actual.is_numeric(),
                feature_types.BOOLEAN: actual == pl.Boolean,
                feature_types.DATETIME: isinstance(actual, pl.Datetime),
                feature_types.DATE: actual == pl.Date,
                feature_types.OBJECT: isinstance(actual, (pl.Struct, pl.Object)),
                feature_types.ARRAY: isinstance(actual, (pl.List, pl.Array)),
            }
            if expected not in compatible:
                supported = ", ".join(feature_types.FEATURE_TYPES)
                raise ValueError(
                    f"Unsupported feature type for {name}: {expected}. Supported types: {supported}"
                )
            if not compatible[expected]:
                raise ValueError(f"Output column {name} has type {actual}; expected {expected}")


DATAFRAME_BACKENDS: dict[str, type[DataFrameBackend]] = {"polars": PolarsBackend}


def create_backend(config: config_module.EngineBackendConfig) -> DataFrameBackend:
    """Create the configured dataframe backend."""
    try:
        backend_class = DATAFRAME_BACKENDS[config.dataframe.lower()]
    except KeyError as error:
        raise ValueError(f"Unsupported dataframe backend: {config.dataframe}") from error
    return backend_class()
