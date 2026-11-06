"""Function definitions and kind rules for spec documents."""

from __future__ import annotations

import functools
import typing

import pydantic

from uptimely.spec import arg_types, functions

from . import common


class FunctionTemplate(common.StrictModel):
    """One logical function definition in the spec catalog."""

    id: str = pydantic.Field(exclude=True)
    name: str | None = None
    kind: functions.FunctionKindId
    returns: functions.ReturnKind
    entrypoint: str
    validate_signature: bool = pydantic.Field(
        default=True,
        description="Whether to inspect the Python signature and check implementation contracts.",
    )
    args: dict[str, common.Argument] = pydantic.Field(default_factory=dict)
    description: str | None = None

    @pydantic.model_validator(mode="after")
    def generate_name(self) -> typing.Self:
        """Generate a display name from the function ID when one is not supplied."""
        if self.name is None:
            self.name = common.humanize_identifier(self.id)
        return self

    @functools.cached_property
    def arguments_by_type(self) -> dict[str, dict[str, common.Argument]]:
        """Return argument declarations grouped by type in declaration order."""
        grouped: dict[str, dict[str, common.Argument]] = {}
        for argument_id, argument in self.args.items():
            argument_type = (
                arg_types.DATAFRAME if arg_types.is_dataframe(argument.type) else argument.type
            )
            grouped.setdefault(argument_type, {})[argument_id] = argument
        return grouped


class FunctionCatalog(pydantic.RootModel[dict[str, FunctionTemplate]]):
    """Function definitions keyed by their globally unique identifiers."""

    root: dict[str, FunctionTemplate] = pydantic.Field(default_factory=dict)

    def by_kind(self, kind: functions.FunctionKindId) -> dict[str, FunctionTemplate]:
        """Return function definitions for one kind."""
        return self.functions_by_kind.get(kind, {})

    def iter_functions(self) -> typing.Iterator[tuple[str, FunctionTemplate, int]]:
        """Yield each function with its number of dataframe arguments."""
        for function_id, function in self.root.items():
            yield (
                function_id,
                function,
                len(function.arguments_by_type.get(arg_types.DATAFRAME, {})),
            )

    @functools.cached_property
    def functions_by_kind(self) -> dict[functions.FunctionKindId, dict[str, FunctionTemplate]]:
        """Return function groups without repeatedly filtering the catalog."""
        grouped: dict[functions.FunctionKindId, dict[str, FunctionTemplate]] = {}
        for function_id, function in self.root.items():
            grouped.setdefault(function.kind, {})[function_id] = function
        return grouped

    @functools.cached_property
    def arguments(self) -> dict[tuple[str, str], common.Argument]:
        """Return argument declarations keyed by function key and argument key."""
        return {
            (function_id, argument_id): argument
            for function_id, function in self.root.items()
            for argument_id, argument in function.args.items()
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
