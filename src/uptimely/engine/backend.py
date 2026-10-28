"""Backend and runtime protocols used by the execution engine."""

from __future__ import annotations

import typing
from collections import abc

import polars as pl

from . import config as config_module


class DataFrameBackend(typing.Protocol):
    """Operations required by the engine from a dataframe backend."""

    name: str

    def __init__(self, *, validate_lazy_frames: bool = True) -> None: ...

    def is_frame(self, value: object) -> bool: ...

    def should_validate_values(self, frame: object) -> bool: ...

    def column_names(self, frame: object) -> list[str]: ...

    def select(self, frame: object, columns: abc.Sequence[str]) -> object: ...

    def lazy(self, frame: object) -> object: ...

    def join(
        self, left: object, right: object, keys: abc.Sequence[str], *, validate: str = "1:1"
    ) -> object: ...

    def collect(self, frame: object) -> object: ...

    def is_duplicated(self, frame: object) -> bool: ...

    def row_count(self, frame: object) -> int: ...

    def same_keys(self, left: object, right: object, keys: abc.Sequence[str]) -> bool: ...

    def validate_types(self, frame: object, types: abc.Mapping[str, str]) -> None: ...


class PolarsBackend:
    """Polars implementation of the engine dataframe contract."""

    name = "polars"

    def __init__(self, *, validate_lazy_frames: bool = True) -> None:
        """Configure whether value validation may execute lazy query plans.

        Args:
            validate_lazy_frames: Execute lazy plans for data-dependent checks.
                When false, engine validation skips these checks for LazyFrames.
                Explicit calls to collect remain available.
        """
        self.validate_lazy_frames = validate_lazy_frames

    def is_frame(self, value: object) -> bool:
        return isinstance(value, (pl.DataFrame, pl.LazyFrame))

    def should_validate_values(self, frame: object) -> bool:
        """Allow eager validation, and lazy validation only when enabled."""
        return self.validate_lazy_frames or not isinstance(frame, pl.LazyFrame)

    def _require_value_validation(self, frame: object) -> None:
        """Prevent direct value queries from implicitly executing disabled lazy plans."""
        if not self.should_validate_values(frame):
            raise ValueError(
                "Implicit lazy execution is disabled by validate_lazy_frames=False; "
                "collect the frame explicitly before querying its values"
            )

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
        if not keys:
            for frame in (left, right):
                if self.should_validate_values(frame) and self.row_count(frame) > 1:
                    raise ValueError("Dimensionless fragments must contain at most one global row")
            key = "__uptimely_global_key"
            columns = set(self.column_names(left)) | set(self.column_names(right))
            while key in columns:
                key += "_"
            return (
                left.with_columns(pl.lit(0).alias(key))
                .join(
                    right.with_columns(pl.lit(0).alias(key)),
                    on=key,
                    how="full",
                    coalesce=True,
                    validate=validate,
                )
                .drop(key)
            )
        return left.join(
            right,
            on=list(keys),
            how="full",
            coalesce=True,
            validate=validate,
            nulls_equal=True,
        )

    def collect(self, frame: object) -> object:
        return frame.collect()

    def is_duplicated(self, frame: object) -> bool:
        self._require_value_validation(frame)
        if isinstance(frame, pl.LazyFrame):
            frame = frame.collect()
        return bool(frame.is_duplicated().any())

    def row_count(self, frame: object) -> int:
        """Return the row count without materializing all columns of a lazy frame."""
        self._require_value_validation(frame)
        count = frame.select(pl.len())
        if isinstance(count, pl.LazyFrame):
            count = count.collect()
        return count.item()

    def same_keys(self, left: object, right: object, keys: abc.Sequence[str]) -> bool:
        """Compare observation identities without assuming physical row order."""
        self._require_value_validation(left)
        self._require_value_validation(right)
        if not keys:
            return self.row_count(left) == self.row_count(right)
        left_keys = left.select(list(keys))
        right_keys = right.select(list(keys))
        if isinstance(left_keys, pl.LazyFrame):
            left_keys = left_keys.collect()
        if isinstance(right_keys, pl.LazyFrame):
            right_keys = right_keys.collect()
        return left_keys.sort(list(keys)).equals(right_keys.sort(list(keys)))

    def validate_types(self, frame: object, types: abc.Mapping[str, str]) -> None:
        """Check declared logical column types against the returned schema."""
        schema = frame.collect_schema()
        for name, expected in types.items():
            actual = schema[name]
            compatible = {
                "string": actual == pl.String,
                "integer": actual.is_integer(),
                "float": actual.is_float(),
                "numeric": actual.is_numeric(),
                "boolean": actual == pl.Boolean,
                "datetime": isinstance(actual, pl.Datetime),
                "date": actual == pl.Date,
                "object": isinstance(actual, (pl.Struct, pl.Object)),
                "array": isinstance(actual, (pl.List, pl.Array)),
            }
            if expected not in compatible:
                raise ValueError(f"Unsupported feature type for {name}: {expected}")
            if not compatible[expected]:
                raise ValueError(f"Output column {name} has type {actual}; expected {expected}")


DATAFRAME_BACKENDS: dict[str, type[DataFrameBackend]] = {"polars": PolarsBackend}


def create_backend(config: config_module.EngineBackendConfig) -> DataFrameBackend:
    """Create the configured dataframe backend."""
    try:
        backend_class = DATAFRAME_BACKENDS[config.dataframe.lower()]
    except KeyError as error:
        raise ValueError(f"Unsupported dataframe backend: {config.dataframe}") from error
    return backend_class(validate_lazy_frames=config.validate_lazy_frames)
