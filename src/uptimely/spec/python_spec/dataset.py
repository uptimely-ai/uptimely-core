"""Python-friendly dataset declaration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from uptimely.spec.json_spec.json_model import (
    AggregateFunction,
    Argument,
    CollapseFunction,
    ConformFunction,
    ExpandFunction,
    FunctionCatalog,
    ReadFunction,
    VectorizeFunction,
    WriteFunction,
)
from uptimely.spec.json_spec.json_model import (
    Dataset as DatasetModel,
)
from uptimely.spec.json_spec.json_model import (
    RowScope as RowScopeModel,
)
from uptimely.spec.json_spec.json_model import (
    Source as SourceModel,
)
from uptimely.spec.json_spec.json_model import (
    Transform as TransformModel,
)

from .bind import _argument_definition, _entrypoint, _models_by_id

if TYPE_CHECKING:
    from .feature import Vectorize
    from .fragment import Collapse, Conform, Expand, Read, Write, _Operation

__all__ = [
    "Dataset",
    "RowScope",
]


@dataclass(frozen=True)
class RowScope:
    """The conceptual row subset shared by dataset fragments."""

    grain: str = ""
    filtering: str = ""
    coverage: str = ""

    def to_model(self) -> RowScopeModel:
        """Convert this row scope definition to its canonical model."""
        return RowScopeModel(
            grain=self.grain,
            filtering=self.filtering,
            coverage=self.coverage,
        )


@dataclass(frozen=True)
class Dataset:
    """A Python declaration of one dataset and its operations."""

    id: str
    read: list[Read] = field(default_factory=list)
    conform: list[Conform] = field(default_factory=list)
    expand: list[Expand] = field(default_factory=list)
    collapse: list[Collapse] = field(default_factory=list)
    vectorize: list[Vectorize] = field(default_factory=list)
    write: list[Write] = field(default_factory=list)
    description: str | None = None
    row_scope: RowScope = field(default_factory=RowScope)

    def to_model(self) -> DatasetModel:
        """Convert this declaration to the canonical Pydantic dataset model."""

        def fragment_models(
            operation_type: str,
            declarations: list[Read | _Operation],
        ) -> dict[str, SourceModel | TransformModel]:
            model_type = SourceModel if operation_type == "read" else TransformModel
            models = []
            for declaration in declarations:
                model = declaration.to_model()
                models.append(
                    model_type(
                        id=model.id,
                        binding=model.binding,
                        features=model.features,
                    )
                )
            return {model.id: model for model in models}

        return DatasetModel(
            id=self.id,
            description=self.description,
            row_scope=self.row_scope.to_model(),
            read=fragment_models("read", self.read),
            conform=fragment_models("conform", self.conform),
            expand=fragment_models("expand", self.expand),
            collapse=fragment_models("collapse", self.collapse),
            vectorize={feature.id: feature.to_model() for feature in self.vectorize},
            write=_models_by_id(self.write),
        )

    def function_catalog(self) -> FunctionCatalog:
        """Build the function templates required by this dataset declaration."""
        from .feature import Aggregation

        def argument(name: str, value: Any) -> Argument:
            return Argument(id=name, **_argument_definition(value))

        read: dict[str, ReadFunction] = {}
        collapse: dict[str, CollapseFunction] = {}
        expand: dict[str, ExpandFunction] = {}
        conform: dict[str, ConformFunction] = {}

        def register(
            operation_type: str,
            fragment: Read | _Operation,
        ) -> None:
            function_id = fragment.bind.function_id or fragment.bind.function.__name__
            function = {
                "read": ReadFunction,
                "collapse": CollapseFunction,
                "expand": ExpandFunction,
                "conform": ConformFunction,
            }.get(operation_type)
            if function is None:
                raise ValueError(f"Unsupported fragment operation type: {operation_type}")
            catalog = {
                "read": read,
                "collapse": collapse,
                "expand": expand,
                "conform": conform,
            }[operation_type]
            catalog[function_id] = function(
                id=function_id,
                entrypoint=_entrypoint(fragment.bind.function),
                args={name: argument(name, value) for name, value in fragment.bind.args.items()},
            )

        for operation_type in ("read", "conform", "expand", "collapse"):
            for fragment in getattr(self, operation_type):
                register(operation_type, fragment)

        write = {
            write_fragment.bind.function_id or write_fragment.bind.function.__name__: WriteFunction(
                id=write_fragment.bind.function_id or write_fragment.bind.function.__name__,
                entrypoint=_entrypoint(write_fragment.bind.function),
                args={
                    name: argument(name, value) for name, value in write_fragment.bind.args.items()
                },
            )
            for write_fragment in self.write
        }
        vectorize = {
            vectorized_feature.bind.function_id
            or vectorized_feature.bind.function.__name__: VectorizeFunction(
                id=vectorized_feature.bind.function_id or vectorized_feature.bind.function.__name__,
                entrypoint=_entrypoint(vectorized_feature.bind.function),
                args={
                    name: argument(name, value)
                    for name, value in vectorized_feature.bind.args.items()
                },
            )
            for vectorized_feature in self.vectorize
        }

        aggregate: dict[str, AggregateFunction] = {}

        def register_aggregations(value: Any) -> None:
            if isinstance(value, Aggregation):
                aggregate[value.id] = AggregateFunction(
                    id=value.id,
                    entrypoint=_entrypoint(value.function),
                    args={name: argument(name, item) for name, item in value.args.items()},
                )
                return
            if isinstance(value, (list, tuple)):
                for item in value:
                    register_aggregations(item)
            elif isinstance(value, dict):
                for item in value.values():
                    register_aggregations(item)

        for fragment in self.collapse:
            register_aggregations(fragment.bind.args)

        return FunctionCatalog(
            read=read,
            write=write,
            vectorize=vectorize,
            aggregate=aggregate,
            collapse=collapse,
            expand=expand,
            conform=conform,
        )
