"""Backend and runtime protocols used by the execution engine."""

from __future__ import annotations

import typing
from collections import abc

import polars as pl


class DataFrameBackend(typing.Protocol):
    """Operations required by the engine from a dataframe backend."""

    name: str

    def is_frame(self, value: object) -> bool: ...

    def column_names(self, frame: object) -> list[str]: ...

    def select(self, frame: object, columns: abc.Sequence[str]) -> object: ...

    def lazy(self, frame: object) -> object: ...

    def join(self, left: object, right: object, keys: abc.Sequence[str]) -> object: ...

    def collect(self, frame: object) -> object: ...

    def is_duplicated(self, frame: object) -> bool: ...

    def row_count(self, frame: object) -> int: ...

    def same_keys(self, left: object, right: object, keys: abc.Sequence[str]) -> bool: ...

    def validate_types(self, frame: object, types: abc.Mapping[str, str]) -> None: ...


class ResourceResolver(typing.Protocol):
    """Resolve plan resources needed during execution."""

    def entity_dimensions(self, entity_id: str) -> list[str]: ...


class CallableLoader(typing.Protocol):
    """Load an executable callable from a plan entrypoint."""

    def load(self, entrypoint: str) -> abc.Callable[..., typing.Any]: ...


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

    def join(self, left: object, right: object, keys: abc.Sequence[str]) -> object:
        if not keys:
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
                    validate="1:1",
                )
                .drop(key)
            )
        return left.join(
            right, on=list(keys), how="full", coalesce=True, validate="1:1", nulls_equal=True
        )

    def collect(self, frame: object) -> object:
        return frame.collect()

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


class PlanResourceResolver:
    """Resolve resources from the portable plan resource mapping."""

    def __init__(self, resources: abc.Mapping[str, typing.Any]) -> None:
        self.resources = resources

    def entity_dimensions(self, entity_id: str) -> list[str]:
        entity = self.resources.get("entities", {}).get(entity_id)
        if entity is None:
            raise ValueError(f"Unknown entity: {entity_id}")
        return list(entity.get("dimensions", []))
