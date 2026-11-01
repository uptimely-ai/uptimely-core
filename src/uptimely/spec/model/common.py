"""Shared types for spec document models."""

from __future__ import annotations

import dataclasses
import functools
import typing

import pydantic

from uptimely.spec import selectors


class StrictModel(pydantic.BaseModel):
    """Base model that rejects fields outside the spec contract."""

    model_config = pydantic.ConfigDict(extra="forbid")


def humanize_identifier(identifier: str) -> str:
    """Return a display name for a snake- or kebab-case identifier."""
    return identifier.replace("_", " ").replace("-", " ").title()


class SpecSource(StrictModel):
    """Describe how a spec document was authored or generated."""

    name: str
    generated: bool


class Dimension(StrictModel):
    """A globally defined grain under `dimensions`."""

    id: str = pydantic.Field(exclude=True)
    type: str
    description: str | None = None
    parent: str | None = None
    name: str | None = None

    @pydantic.model_validator(mode="after")
    def generate_name(self) -> typing.Self:
        """Generate a display name from the dimension ID when one is not supplied."""
        if self.name is None:
            self.name = humanize_identifier(self.id)
        return self


class Argument(StrictModel):
    """A single argument entry under a function template's `args`."""

    id: str = pydantic.Field(exclude=True)
    type: str
    comment: str | None = None


BindingArgument = dict[str, typing.Any] | list[typing.Any] | str | int | float | bool | None


class Binding(StrictModel):
    """Wires a catalog function to its arguments."""

    function: str
    args: dict[str, BindingArgument] = pydantic.Field(default_factory=dict)

    @functools.cached_property
    def values_with_paths(self) -> tuple[tuple[object, tuple[str | int, ...]], ...]:
        """Return nested argument leaves and their relative paths, in supplied order."""
        return tuple(_binding_values(self.args, ()))

    @functools.cached_property
    def dataset_input_references(self) -> tuple[str, ...]:
        """Return dataset data references in order, retaining duplicates and ``@``."""
        return tuple(
            selectors.structural_identifier(value, selectors.DATASET_PREFIX)
            for value, _ in self.values_with_paths
            if (
                isinstance(value, str)
                and value.startswith(selectors.DATASET_PREFIX)
                and not value.endswith(selectors.ID_SELECTOR)
                and not value.endswith(selectors.DIMENSION_IDS_SELECTOR)
            )
        )

    def dataset_dependencies(self, current_dataset: str) -> list[str]:
        """Return unique referenced datasets, resolving ``@`` to the current dataset."""
        return list(
            dict.fromkeys(
                current_dataset if identifier == selectors.CURRENT_ID else identifier
                for identifier in self.dataset_input_references
            )
        )

    def resolve_args(
        self,
        dataset_id: str,
        feature_id: str | None = None,
        dimension_ids_by_dataset: typing.Mapping[str, typing.Sequence[str]] | None = None,
    ) -> dict[str, typing.Any]:
        """Resolve structural references in these arguments for an invocation."""
        resolver = BindingArgumentResolver(
            current_dataset_id=dataset_id,
            feature_id=feature_id,
            dimension_ids_by_dataset=dimension_ids_by_dataset,
        )
        return resolver.resolve_arguments(self.args)

    @functools.cached_property
    def references_by_prefix(
        self,
    ) -> dict[str, tuple[tuple[str, tuple[str | int, ...]], ...]]:
        """Group structural references after one traversal of nested arguments."""
        references: dict[str, list[tuple[str, tuple[str | int, ...]]]] = {
            prefix: [] for prefix in selectors.STRUCTURAL_PREFIXES
        }
        for value, path in self.values_with_paths:
            if isinstance(value, str):
                for prefix, matches in references.items():
                    if value.startswith(prefix):
                        matches.append((selectors.structural_identifier(value, prefix), path))
                        break
        return {prefix: tuple(matches) for prefix, matches in references.items()}


def _binding_values(
    value: object, path: tuple[str | int, ...]
) -> typing.Iterator[tuple[object, tuple[str | int, ...]]]:
    """Flatten supplied argument containers once, retaining leaf order and paths."""
    if isinstance(value, pydantic.BaseModel):
        value = value.model_dump()
    if isinstance(value, dict):
        for name, nested in value.items():
            yield from _binding_values(nested, (*path, name))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            yield from _binding_values(nested, (*path, index))
    else:
        yield value, path


@dataclasses.dataclass(frozen=True)
class BindingArgumentResolver:
    """Resolve nested binding values using invocation-specific selector context."""

    current_dataset_id: str
    feature_id: str | None
    dimension_ids_by_dataset: typing.Mapping[str, typing.Sequence[str]] | None

    def resolve_arguments(self, arguments: typing.Mapping[str, object]) -> dict[str, typing.Any]:
        """Resolve every binding argument using this invocation's context."""
        return {name: self._resolve_value(value) for name, value in arguments.items()}

    def _resolve_value(self, value: object) -> object:
        """Resolve structural references recursively within one binding value."""
        if isinstance(value, pydantic.BaseModel):
            value = value.model_dump()
        if isinstance(value, str):
            return self._resolve_reference(value)
        if isinstance(value, dict):
            return {key: self._resolve_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._resolve_value(item) for item in value]
        return value

    def _resolve_reference(self, value: str) -> str | list[str]:
        """Resolve one structural reference to its execution value."""
        if value in {
            f"{selectors.FEATURE_PREFIX}{selectors.CURRENT_ID}",
            f"{selectors.FEATURE_PREFIX}{selectors.CURRENT_ID}{selectors.ID_SELECTOR}",
        }:
            return self.feature_id if self.feature_id is not None else value

        for prefix in selectors.STRUCTURAL_PREFIXES:
            if not value.startswith(prefix):
                continue
            identifier = value.removeprefix(prefix)
            if prefix == selectors.DATASET_PREFIX:
                if identifier.endswith(selectors.DIMENSION_IDS_SELECTOR):
                    identifier = identifier.removesuffix(selectors.DIMENSION_IDS_SELECTOR)
                    dataset_id = (
                        self.current_dataset_id
                        if identifier == selectors.CURRENT_ID
                        else identifier
                    )
                    if (
                        self.dimension_ids_by_dataset is None
                        or dataset_id not in self.dimension_ids_by_dataset
                    ):
                        raise ValueError(f"Cannot resolve dimension IDs for dataset {dataset_id}")
                    return list(self.dimension_ids_by_dataset[dataset_id])
                identifier = identifier.removesuffix(selectors.DATAFRAME_SELECTOR).removesuffix(
                    selectors.ID_SELECTOR
                )
            else:
                identifier = identifier.removesuffix(selectors.ID_SELECTOR)
            return (
                self.current_dataset_id
                if prefix == selectors.DATASET_PREFIX and identifier == selectors.CURRENT_ID
                else identifier
            )
        return value
