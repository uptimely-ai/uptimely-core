"""Python-friendly dataset declaration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from uptimely.spec.json_spec import json_model

from . import mappings as mapping_declarations
from .bind import _argument_definition, _entrypoint
from .feature import Feature
from .mappings import (
    Aggregation,
    Collapse,
    Conform,
    Expand,
    Read,
    Vectorize,
    Write,
)
from .ref import Reference
from .row_context import _context

__all__ = [
    "Dataset",
    "Order",
    "RowScope",
]


@dataclass(frozen=True)
class RowScope:
    """The conceptual row subset represented by a dataset."""

    grain: str = ""
    filtering: str = ""
    coverage: str = ""

    def to_model(self) -> json_model.RowScope:
        """Convert this row scope definition to its canonical model."""
        return json_model.RowScope(
            grain=self.grain,
            filtering=self.filtering,
            coverage=self.coverage,
        )


@dataclass(frozen=True)
class Order:
    """Declare a logical ordering key, not a required physical sort.

    Args:
        dimension: A dimension reference created by ``ref.dimension`` or its
            canonical ``$dimensions.<id>`` string.
        direction: Ascending (``asc``) or descending (``desc``) order.
    """

    dimension: Reference | str
    direction: Literal["asc", "desc"]

    def to_model(self) -> json_model.Order:
        """Convert this ordering key to its canonical model."""
        return json_model.Order(
            dimension=(
                self.dimension.to_model()
                if isinstance(self.dimension, Reference)
                else self.dimension
            ),
            direction=self.direction,
        )


@dataclass(frozen=True)
class Dataset:
    """A Python declaration of one dataset, its features, and mappings."""

    id: str
    features: list[Feature] = field(default_factory=list)
    mappings: list[Vectorize | Read | Conform | Expand | Collapse | Write] = field(
        default_factory=list
    )
    description: str | None = None
    row_scope: RowScope = field(default_factory=RowScope)
    order: list[Order] = field(default_factory=list)

    def to_model(self) -> json_model.Dataset:
        """Convert this declaration to the canonical Pydantic dataset model."""
        mappings: dict[str, json_model.FeatureMapping] = {}
        feature_models = {item.id: item.to_model() for item in self.features}
        for declaration in self.mappings:
            model = declaration.to_model()
            mappings[model.id] = model
            for output in declaration.features:
                if isinstance(output, Feature):
                    feature_models.setdefault(output.id, output.to_model())
                elif isinstance(output, Reference):
                    feature_id = output.value.removeprefix("$features.")
                    if feature_id not in feature_models:
                        raise ValueError(
                            f"Mapping '{model.id}' references undeclared feature '{feature_id}'"
                        )
                elif output.startswith("$features."):
                    feature_id = output.removeprefix("$features.")
                    if feature_id not in feature_models:
                        raise ValueError(
                            f"Mapping '{model.id}' references undeclared feature '{feature_id}'"
                        )
                elif output not in feature_models:
                    raise ValueError(
                        f"Mapping '{model.id}' references undeclared feature '{output}'"
                    )
            if isinstance(declaration, mapping_declarations.Vectorize):
                context = _context(None, declaration.row_context)
                if context is not None:
                    for feature_id in model.features:
                        if feature_id in feature_models:
                            feature_models[feature_id] = feature_models[feature_id].model_copy(
                                update={"row_context": context}
                            )

        return json_model.Dataset(
            id=self.id,
            description=self.description,
            row_scope=self.row_scope.to_model(),
            order=[key.to_model() for key in self.order],
            features=feature_models,
            mappings=mappings,
        )

    def function_catalog(self) -> json_model.FunctionCatalog:
        """Build the function templates required by this dataset declaration."""

        def argument(name: str, value: Any) -> json_model.Argument:
            return json_model.Argument(id=name, **_argument_definition(value))

        read: dict[str, json_model.ReadFunction] = {}
        vectorize: dict[str, json_model.VectorizeFunction] = {}
        collapse: dict[str, json_model.CollapseFunction] = {}
        expand: dict[str, json_model.ExpandFunction] = {}
        conform: dict[str, json_model.ConformFunction] = {}

        write: dict[str, json_model.WriteFunction] = {}

        def register(
            declaration: Vectorize | Read | Conform | Expand | Collapse | Write,
        ) -> None:
            if isinstance(declaration, Write):
                function_id = declaration.bind.function_id or declaration.bind.function.__name__
                write[function_id] = json_model.WriteFunction(
                    id=function_id,
                    entrypoint=_entrypoint(declaration.bind.function),
                    args={
                        name: argument(name, value) for name, value in declaration.bind.args.items()
                    },
                )
                return
            operation_type = {
                mapping_declarations.Read: "read",
                mapping_declarations.Conform: "conform",
                mapping_declarations.Expand: "expand",
                mapping_declarations.Collapse: "collapse",
                mapping_declarations.Vectorize: "vectorize",
            }.get(type(declaration))
            if operation_type is None:
                raise ValueError(
                    f"Mapping '{declaration.id or declaration.bind.function.__name__}' "
                    "must use a category-specific mapping declaration"
                )
            function_id = declaration.bind.function_id or declaration.bind.function.__name__
            function = {
                "read": json_model.ReadFunction,
                "vectorize": json_model.VectorizeFunction,
                "collapse": json_model.CollapseFunction,
                "expand": json_model.ExpandFunction,
                "conform": json_model.ConformFunction,
            }.get(operation_type)
            if function is None:
                raise ValueError(f"Unsupported mapping operation type: {operation_type}")
            catalog = {
                "read": read,
                "vectorize": vectorize,
                "collapse": collapse,
                "expand": expand,
                "conform": conform,
            }[operation_type]
            arguments = {
                name: argument(name, value)
                for name, value in declaration.bind.args.items()
                if not (
                    isinstance(declaration, mapping_declarations.Collapse)
                    and name == "aggregations"
                )
            }
            if isinstance(declaration, mapping_declarations.Collapse):
                aggregation_values = declaration.aggregations or declaration.bind.args.get(
                    "aggregations", {}
                )
                arguments["aggregations"] = argument("aggregations", aggregation_values)
            catalog[function_id] = function(
                id=function_id,
                entrypoint=_entrypoint(declaration.bind.function),
                args=arguments,
            )

        for declaration in self.mappings:
            register(declaration)

        aggregate: dict[str, json_model.AggregateFunction] = {}

        def register_aggregations(value: Any) -> None:
            if isinstance(value, Aggregation):
                aggregate[value.id] = json_model.AggregateFunction(
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

        for declaration in self.mappings:
            if isinstance(declaration, mapping_declarations.Collapse):
                register_aggregations(declaration.aggregations or declaration.bind.args)

        return json_model.FunctionCatalog(
            read=read,
            write=write,
            vectorize=vectorize,
            aggregate=aggregate,
            collapse=collapse,
            expand=expand,
            conform=conform,
        )
