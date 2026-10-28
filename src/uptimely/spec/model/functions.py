"""Function definitions and kind rules for spec documents."""

from __future__ import annotations

import typing

import pydantic

from uptimely.spec import operations

from . import common

FUNCTION_TYPES = ["sql_query", "python_function"]
FUNCTION_KINDS = operations.FUNCTION_KINDS
FunctionKind = operations.FunctionKind
FunctionReturns = operations.FunctionReturns


class FunctionTemplate(common.StrictModel):
    """One logical function definition in the spec catalog."""

    id: str = pydantic.Field(exclude=True)
    kind: FunctionKind
    returns: FunctionReturns
    entrypoint: str
    validate_signature: bool = pydantic.Field(
        default=True,
        description="Whether to inspect the Python signature and check implementation contracts.",
    )
    args: dict[str, common.Argument] = pydantic.Field(default_factory=dict)
    description: str | None = None


class FunctionCatalog(pydantic.RootModel[dict[str, FunctionTemplate]]):
    """Function definitions keyed by their globally unique identifiers."""

    root: dict[str, FunctionTemplate] = pydantic.Field(default_factory=dict)

    def by_kind(self, kind: FunctionKind) -> dict[str, FunctionTemplate]:
        """Return function definitions for one kind."""
        return {
            function_id: function
            for function_id, function in self.root.items()
            if function.kind == kind
        }

    def __getitem__(self, function_id: str) -> FunctionTemplate:
        return self.root[function_id]

    def get(self, function_id: str, default: typing.Any = None) -> FunctionTemplate | typing.Any:
        """Return one function definition, or a default when it is absent."""
        return self.root.get(function_id, default)

    def __contains__(self, function_id: object) -> bool:
        return function_id in self.root

    def __iter__(self) -> typing.Iterator[str]:
        return iter(self.root)

    def __len__(self) -> int:
        return len(self.root)
