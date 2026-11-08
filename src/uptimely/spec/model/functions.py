"""Function definitions and kind rules for spec documents."""

from __future__ import annotations

import functools
import logging
import typing

import pydantic

from uptimely.spec import arg_types
from uptimely.spec import function_kinds as functions

from . import base

logger = logging.getLogger(__name__)


class Argument(base.StrictModel):
    """A single argument declaration under a function template's `args`."""

    id: str = pydantic.Field(exclude=True)
    type: str
    comment: str | None = None


class FunctionTemplate(base.StrictModel):
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
    args: dict[str, Argument] = pydantic.Field(default_factory=dict)
    description: str | None = None

    def check_return_contract(self) -> None:
        """Require the return kind defined by the function kind."""
        logger.debug("Check function return contract: %s", self.id)
        expected = functions.FUNCTION_KINDS[self.kind].returns
        if self.returns != expected:
            dataframe_inputs = sum(
                arg_types.is_dataframe(argument.type) for argument in self.args.values()
            )
            raise ValueError(
                f"Kind {self.kind} must declare returns={expected}."
                + functions.kind_hint(self.returns, dataframe_inputs)
            )

    def check_dataframe_input_contract(self) -> None:
        """Require the dataframe argument count defined by the function kind."""
        logger.debug("Check function dataframe argument count: %s", self.id)
        expected = functions.FUNCTION_KINDS[self.kind].dataframe_inputs
        dataframe_inputs = sum(
            arg_types.is_dataframe(argument.type) for argument in self.args.values()
        )
        if expected is not None and dataframe_inputs != expected:
            raise ValueError(
                f"Kind {self.kind} requires {expected} dataframe argument(s), "
                f"got {dataframe_inputs}." + functions.kind_hint(self.returns, dataframe_inputs)
            )

    def check_argument_contracts(self) -> None:
        """Validate argument rules that depend only on this function declaration."""
        logger.debug("Check function argument contracts: %s", self.id)
        if self.kind != functions.MERGE and any(
            argument.type == arg_types.OPTIONAL_DATAFRAME for argument in self.args.values()
        ):
            raise ValueError("Nullable dataframe arguments are reserved for merge functions")
        if self.kind != functions.MERGE:
            return
        target = self.args.get("target")
        if target is None or target.type != arg_types.OPTIONAL_DATAFRAME:
            raise ValueError("Merge functions must declare target as 'dataframe | null'")
        fragment = self.args.get("fragment")
        if fragment is None or fragment.type != arg_types.DATAFRAME:
            raise ValueError("Merge functions must declare fragment as 'dataframe'")

    @pydantic.model_validator(mode="after")
    def generate_name(self) -> typing.Self:
        """Generate a display name from the function ID when one is not supplied."""
        if self.name is None:
            self.name = base.humanize_identifier(self.id)
        return self

    @functools.cached_property
    def arguments_by_type(self) -> dict[str, dict[str, Argument]]:
        """Return argument declarations grouped by type in declaration order."""
        grouped: dict[str, dict[str, Argument]] = {}
        for argument_id, argument in self.args.items():
            argument_type = (
                arg_types.DATAFRAME if arg_types.is_dataframe(argument.type) else argument.type
            )
            grouped.setdefault(argument_type, {})[argument_id] = argument
        return grouped


class FunctionCatalog(pydantic.RootModel[dict[str, FunctionTemplate]]):
    """Function definitions keyed by their globally unique identifiers."""

    root: dict[str, FunctionTemplate] = pydantic.Field(default_factory=dict)

    @classmethod
    def merge(cls, catalogs: typing.Iterable[FunctionCatalog]) -> typing.Self:
        """Create a catalog from compatible definitions without modifying inputs.

        Args:
            catalogs: Catalogs to consume once, in declaration order.

        Returns:
            A new catalog retaining the first definition for each identifier.

        Raises:
            ValueError: Catalogs contain conflicting definitions for an identifier.
        """
        definitions: dict[str, FunctionTemplate] = {}
        for catalog in catalogs:
            for function_id, function in catalog.root.items():
                current = definitions.get(function_id)
                if current is None:
                    definitions[function_id] = function
                elif current != function:
                    raise ValueError(f"Conflicting function definition for '{function_id}'")
        return cls(root=definitions)

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
    def arguments(self) -> dict[tuple[str, str], Argument]:
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
