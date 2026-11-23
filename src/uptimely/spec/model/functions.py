"""Function definitions and dataframe contracts for spec documents."""

from __future__ import annotations

import functools
import logging
import typing

import pydantic

from uptimely.spec import arg_types, function_contracts

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
    category: str | None = None
    returns: function_contracts.ReturnRole
    entrypoint: str
    validate_signature: bool = pydantic.Field(
        default=True,
        description="Whether to inspect the Python signature and check implementation contracts.",
    )
    args: dict[str, Argument] = pydantic.Field(default_factory=dict)
    description: str | None = None

    @property
    def frame_signature(self) -> function_contracts.FrameSignature:
        """Return dataframe input and output counts, or unknown for a workflow."""
        if self.returns == "any":
            return (None, None)
        dataframe_inputs = self.dataframe_argument_count
        dataframe_outputs = int(self.returns == "dataframe")
        return dataframe_inputs, dataframe_outputs

    @property
    def dataframe_argument_count(self) -> int:
        """Return the number of declared dataframe argument slots."""
        return sum(arg_types.is_dataframe(argument.type) for argument in self.args.values())

    def check_return_contract(self) -> None:
        """Require a supported independent return contract."""
        logger.debug("Check function return contract: %s", self.id)
        if self.returns not in function_contracts.RETURN_ROLES:
            raise ValueError(f"Unsupported return contract: {self.returns}")

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

    def iter_functions(self) -> typing.Iterator[tuple[str, FunctionTemplate, int]]:
        """Yield each function with its number of dataframe arguments."""
        for function_id, function in self.root.items():
            yield (
                function_id,
                function,
                len(function.arguments_by_type.get(arg_types.DATAFRAME, {})),
            )

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
