"""Python-friendly dataset declaration."""

from __future__ import annotations

import dataclasses
import typing

from uptimely import contracts
from uptimely.spec import catalog as function_catalog
from uptimely.spec import model as spec_model

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

    def to_model(self) -> spec_model.RowScope:
        """Convert this row scope definition to its document model."""
        return spec_model.RowScope(
            grain=self.grain,
            filtering=self.filtering,
            coverage=self.coverage,
        )


@dataclasses.dataclass(frozen=True)
class Order:
    """Declare a logical ordering key, not a required physical sort.

    Args:
        dimension: A dimension reference created by ``ref.dimension`` or its
            ``$dimensions.<id>`` reference string used in spec documents.
        direction: Ascending (``asc``) or descending (``desc``) order.
    """

    dimension: ref.Reference | str
    direction: typing.Literal["asc", "desc"]

    def to_model(self) -> spec_model.Order:
        """Convert this ordering key to its document model."""
        return spec_model.Order(
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
    mappings: list[mapping_declarations.Mapping] = dataclasses.field(default_factory=list)
    description: str | None = None
    row_scope: RowScope = dataclasses.field(default_factory=RowScope)
    order: list[Order] = dataclasses.field(default_factory=list)

    def to_model(self) -> spec_model.Dataset:
        """Convert this declaration to the Pydantic dataset document model."""
        mappings: dict[str, spec_model.Mapping] = {}
        feature_models = {item.id: item.to_model() for item in self.features}
        for declaration in self.mappings:
            model = declaration.to_model()
            mappings[model.id] = model
            for output in declaration.outputs:
                if isinstance(output, feature.Feature):
                    feature_models.setdefault(output.id, output.to_model())
                elif isinstance(output, ref.Reference):
                    feature_id = output.value.removeprefix(contracts.FEATURE_PREFIX)
                    if feature_id not in feature_models:
                        raise ValueError(
                            f"Mapping '{model.id}' references undeclared feature '{feature_id}'"
                        )
                elif output.startswith(contracts.FEATURE_PREFIX):
                    feature_id = output.removeprefix(contracts.FEATURE_PREFIX)
                    if feature_id not in feature_models:
                        raise ValueError(
                            f"Mapping '{model.id}' references undeclared feature '{feature_id}'"
                        )
                elif output not in feature_models:
                    raise ValueError(
                        f"Mapping '{model.id}' references undeclared feature '{output}'"
                    )
        return spec_model.Dataset(
            id=self.id,
            description=self.description,
            row_scope=self.row_scope.to_model(),
            order=[key.to_model() for key in self.order],
            features=feature_models,
            mappings=mappings,
        )

    def function_catalog(self) -> spec_model.FunctionCatalog:
        """Build the function templates required by this dataset declaration."""

        def argument(name: str, value: typing.Any) -> spec_model.Argument:
            return spec_model.Argument(id=name, **bind._argument_definition(value))

        catalogs: list[spec_model.FunctionCatalog] = []

        def register(declaration: mapping_declarations.Mapping) -> None:
            operation = declaration.operation
            function_id = bind._function_id(declaration.bind)
            arguments = {
                name: argument(name, value) for name, value in declaration.bind.args.items()
            }
            catalogs.append(
                spec_model.FunctionCatalog(
                    root={
                        function_id: function_catalog.function_template(
                            function_id=function_id,
                            operation=operation,
                            entrypoint=bind._entrypoint(declaration.bind.function),
                            args=arguments,
                        )
                    }
                )
            )

        for declaration in self.mappings:
            register(declaration)

        return spec_model.FunctionCatalog(root=function_catalog.merge_function_catalogs(catalogs))
