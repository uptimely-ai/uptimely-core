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

    def with_columns(self, frame: object, column: object) -> object: ...

    def feature_column(self, name: str) -> object: ...

    def literal(self, value: object) -> object: ...

    def alias(self, value: object, name: str) -> object: ...

    def is_column(self, value: object) -> bool: ...


class ResourceResolver(Protocol):
    """Resolve plan resources needed during execution."""

    def entity_dimensions(self, entity_id: str) -> list[str]: ...

    def function_entrypoint(self, category: str, function_id: str) -> str: ...


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
        return left.join(right, on=list(keys), how="full", coalesce=True, validate="1:1")

    def collect(self, frame: object) -> object:
        return frame.collect()

    def is_duplicated(self, frame: object) -> bool:
        if isinstance(frame, pl.LazyFrame):
            frame = frame.collect()
        return bool(frame.is_duplicated().any())

    def with_columns(self, frame: object, column: object) -> object:
        return frame.with_columns(column)

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

    def function_entrypoint(self, category: str, function_id: str) -> str:
        function = self.resources.get("functions", {}).get(category, {}).get(function_id)
        if function is None:
            raise ValueError(f"Unknown {category} function: {function_id}")
        return function["entrypoint"]


class EntrypointLoader:
    """Default callable loader using the package entrypoint implementation."""

    def load(self, entrypoint: str) -> Callable[..., Any]:
        from uptimely.compile.entrypoint import load_callable

        return load_callable(entrypoint, Path.cwd())
