"""Backend and runtime protocols used by the execution engine."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol

import polars as pl


class DataFrameBackend(Protocol):
    """Operations required by the engine from a dataframe backend."""

    name: str

    def is_frame(self, value: object) -> bool: ...

    def column_names(self, frame: object) -> list[str]: ...

    def select(self, frame: object, columns: Sequence[str]) -> object: ...

    def lazy(self, frame: object) -> object: ...

    def join(self, left: object, right: object, keys: Sequence[str]) -> object: ...

    def collect(self, frame: object) -> object: ...

    def is_duplicated(self, frame: object) -> bool: ...

    def row_count(self, frame: object) -> int: ...

    def with_columns(self, frame: object, column: object) -> object: ...

    def collapse(self, frame: object, keys: Sequence[str], columns: Sequence[object]) -> object: ...

    def is_expression(self, value: object) -> bool: ...

    def feature_column(self, name: str) -> object: ...

    def literal(self, value: object) -> object: ...

    def alias(self, value: object, name: str) -> object: ...

    def is_column(self, value: object) -> bool: ...


class ResourceResolver(Protocol):
    """Resolve plan resources needed during execution."""

    def entity_dimensions(self, entity_id: str) -> list[str]: ...


class CallableLoader(Protocol):
    """Load an executable callable from a plan entrypoint."""

    def load(self, entrypoint: str) -> Callable[..., Any]: ...


class PolarsBackend:
    """Polars implementation of the engine dataframe contract."""

    name = "polars"

    def is_frame(self, value: object) -> bool:
        return isinstance(value, (pl.DataFrame, pl.LazyFrame))

    def column_names(self, frame: object) -> list[str]:
        if isinstance(frame, pl.LazyFrame):
            return frame.collect_schema().names()
        return list(frame.columns)

    def select(self, frame: object, columns: Sequence[str]) -> object:
        return frame.select(*columns)

    def lazy(self, frame: object) -> object:
        return frame.lazy()

    def join(self, left: object, right: object, keys: Sequence[str]) -> object:
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
        return left.join(right, on=list(keys), how="full", coalesce=True, validate="1:1")

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

    def with_columns(self, frame: object, column: object) -> object:
        return frame.with_columns(column)

    def collapse(self, frame: object, keys: Sequence[str], columns: Sequence[object]) -> object:
        """Evaluate all reducer expressions together at the requested grain."""
        if keys:
            return frame.group_by(list(keys)).agg(list(columns))
        return frame.select(list(columns))

    def is_expression(self, value: object) -> bool:
        return isinstance(value, pl.Expr)

    def feature_column(self, name: str) -> object:
        return pl.col(name)

    def literal(self, value: object) -> object:
        return pl.lit(value)

    def alias(self, value: object, name: str) -> object:
        return value.alias(name)

    def is_column(self, value: object) -> bool:
        return isinstance(value, (pl.Expr, pl.Series))


class PlanResourceResolver:
    """Resolve resources from the portable plan resource mapping."""

    def __init__(self, resources: Mapping[str, Any]) -> None:
        self.resources = resources

    def entity_dimensions(self, entity_id: str) -> list[str]:
        entity = self.resources.get("entities", {}).get(entity_id)
        if entity is None:
            raise ValueError(f"Unknown entity: {entity_id}")
        return list(entity.get("dimensions", []))


class EntrypointLoader:
    """Default callable loader using the package entrypoint implementation."""

    def load(self, entrypoint: str) -> Callable[..., Any]:
        from uptimely.compile.entrypoint import load_callable

        return load_callable(entrypoint, Path.cwd())
