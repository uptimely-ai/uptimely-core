"""Python-friendly dataset declaration."""

from __future__ import annotations

import dataclasses
import typing

from uptimely.spec import json_spec

from . import bind, feature, ref
from . import mappings as mapping_declarations

__all__ = [
    "Dataset",
    "Order",
    "RowScope",
]


@dataclasses.dataclass(frozen=True)
class RowScope:
    """The conceptual row subset represented by a dataset."""

    grain: str = ""
    filtering: str = ""
    coverage: str = ""

    def to_model(self) -> json_spec.json_model.RowScope:
        """Convert this row scope definition to its canonical model."""
        return json_spec.json_model.RowScope(
            grain=self.grain,
            filtering=self.filtering,
            coverage=self.coverage,
        )


@dataclasses.dataclass(frozen=True)
class Order:
    """Declare a logical ordering key, not a required physical sort.

    Args:
        dimension: A dimension reference created by ``ref.dimension`` or its
            canonical ``$dimensions.<id>`` string.
        direction: Ascending (``asc``) or descending (``desc``) order.
    """

    dimension: ref.Reference | str
    direction: typing.Literal["asc", "desc"]

    def to_model(self) -> json_spec.json_model.Order:
        """Convert this ordering key to its canonical model."""
        return json_spec.json_model.Order(
            dimension=(
                self.dimension.to_model()
                if isinstance(self.dimension, ref.Reference)
                else self.dimension
            ),
            direction=self.direction,
        )


@dataclasses.dataclass(frozen=True)
class Dataset:
    """A Python declaration of one dataset, its features, and mappings."""

    id: str
    features: list[feature.Feature] = dataclasses.field(default_factory=list)
    mappings: list[
        mapping_declarations.Vectorize
        | mapping_declarations.Read
        | mapping_declarations.Conform
        | mapping_declarations.Expand
        | mapping_declarations.Collapse
        | mapping_declarations.Write
    ] = dataclasses.field(default_factory=list)
    description: str | None = None
    row_scope: RowScope = dataclasses.field(default_factory=RowScope)
    order: list[Order] = dataclasses.field(default_factory=list)

    def to_model(self) -> json_spec.json_model.Dataset:
        """Convert this declaration to the canonical Pydantic dataset model."""
        mappings: dict[str, json_spec.json_model.Mapping] = {}
        feature_models = {item.id: item.to_model() for item in self.features}
        for declaration in self.mappings:
            model = declaration.to_model()
            mappings[model.id] = model
            for output in declaration.outputs:
                if isinstance(output, feature.Feature):
                    feature_models.setdefault(output.id, output.to_model())
                elif isinstance(output, ref.Reference):
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
        return json_spec.json_model.Dataset(
            id=self.id,
            description=self.description,
            row_scope=self.row_scope.to_model(),
            order=[key.to_model() for key in self.order],
            features=feature_models,
            mappings=mappings,
        )

    def function_catalog(self) -> json_spec.json_model.FunctionCatalog:
        """Build the function templates required by this dataset declaration."""

        def argument(name: str, value: typing.Any) -> json_spec.json_model.Argument:
            return json_spec.json_model.Argument(id=name, **bind._argument_definition(value))

        read: dict[str, json_spec.json_model.ReadFunction] = {}
        vectorize: dict[str, json_spec.json_model.VectorizeFunction] = {}
        collapse: dict[str, json_spec.json_model.CollapseFunction] = {}
        expand: dict[str, json_spec.json_model.ExpandFunction] = {}
        conform: dict[str, json_spec.json_model.ConformFunction] = {}

        write: dict[str, json_spec.json_model.WriteFunction] = {}

        def register(
            declaration: mapping_declarations.Vectorize
            | mapping_declarations.Read
            | mapping_declarations.Conform
            | mapping_declarations.Expand
            | mapping_declarations.Collapse
            | mapping_declarations.Write,
        ) -> None:
            if isinstance(declaration, mapping_declarations.Write):
                function_id = bind._operation_id(declaration.bind, None)
                write[function_id] = json_spec.json_model.WriteFunction(
                    id=function_id,
                    entrypoint=bind._entrypoint(declaration.bind.function),
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
                    f"Mapping '{bind._operation_id(declaration.bind, declaration.id)}' "
                    "must use a category-specific mapping declaration"
                )
            function_id = bind._operation_id(declaration.bind, None)
            function = {
                "read": json_spec.json_model.ReadFunction,
                "vectorize": json_spec.json_model.VectorizeFunction,
                "expand": json_spec.json_model.ExpandFunction,
                "collapse": json_spec.json_model.CollapseFunction,
                "conform": json_spec.json_model.ConformFunction,
            }.get(operation_type)
            if function is None:
                raise ValueError(f"Unsupported mapping operation type: {operation_type}")
            catalog = {
                "read": read,
                "vectorize": vectorize,
                "expand": expand,
                "collapse": collapse,
                "conform": conform,
            }[operation_type]
            arguments = {
                name: argument(name, value) for name, value in declaration.bind.args.items()
            }
            catalog[function_id] = function(
                id=function_id,
                entrypoint=bind._entrypoint(declaration.bind.function),
                args=arguments,
            )

        for declaration in self.mappings:
            register(declaration)

        return json_spec.json_model.FunctionCatalog(
            read=read,
            write=write,
            vectorize=vectorize,
            collapse=collapse,
            expand=expand,
            conform=conform,
        )
