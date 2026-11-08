"""Function bindings and aggregate views of their bound arguments."""

from __future__ import annotations

import functools
import typing

import pydantic

from uptimely.spec import row_context as row_context_values
from uptimely.spec import selectors

from . import base, binding_argument

if typing.TYPE_CHECKING:
    from . import functions


class Binding(base.StrictModel):
    """Wire a catalog function to its named argument values."""

    function: str
    args: dict[str, binding_argument.BindingArgument] = pydantic.Field(default_factory=dict)

    def argument_mismatches(
        self, function: functions.FunctionTemplate
    ) -> tuple[set[str], set[str]]:
        """Return missing and unknown argument names for a function declaration."""
        return function.args.keys() - self.args.keys(), self.args.keys() - function.args.keys()

    def typed_arguments(
        self, function: functions.FunctionTemplate
    ) -> typing.Iterator[tuple[binding_argument.BindingArgument, str]]:
        """Yield bound leaves with declared types, skipping undeclared arguments."""
        for name, argument in self.args.items():
            declaration = function.args.get(name)
            if declaration is not None:
                yield from argument.typed_arguments(declaration.type)

    @functools.cached_property
    def metadata_references_with_paths(
        self,
    ) -> tuple[tuple[binding_argument.BindingArgument, binding_argument.ArgumentPath], ...]:
        """Return metadata selectors and binding-relative paths."""
        return tuple(
            (argument, path)
            for argument, path in self.references_with_paths
            if argument.is_metadata_reference
        )

    @functools.cached_property
    def grain_references_with_paths(
        self,
    ) -> tuple[tuple[binding_argument.BindingArgument, binding_argument.ArgumentPath], ...]:
        """Return profile grain selectors and their binding-relative paths."""
        return tuple(
            (argument, path)
            for argument, path in self.references_with_paths
            if argument.is_grain_reference
        )

    @property
    def feature_references(self) -> tuple[str, ...]:
        """Return feature reference IDs in order, retaining duplicates and current markers."""
        return tuple(
            identifier
            for argument in self.args.values()
            for identifier in argument.feature_references
        )

    @property
    def uses_current_feature(self) -> bool:
        """Whether any nested reference uses the current output feature marker."""
        return any(
            argument.is_current_feature_reference for argument, _ in self.references_with_paths
        )

    @functools.cached_property
    def references_with_paths(
        self,
    ) -> tuple[tuple[binding_argument.BindingArgument, binding_argument.ArgumentPath], ...]:
        """Return structural argument references with binding-relative paths."""
        return tuple(
            (reference, (name, *path))
            for name, argument in self.args.items()
            for reference, path in argument.references_with_paths
        )

    @functools.cached_property
    def values_with_paths(self) -> tuple[tuple[object, binding_argument.ArgumentPath], ...]:
        """Return nested argument leaves and their binding-relative paths."""
        return tuple(
            (leaf.root, (name, *path))
            for name, argument in self.args.items()
            for leaf, path in argument.leaves_with_paths
        )

    @functools.cached_property
    def references_by_prefix(
        self,
    ) -> dict[str, tuple[tuple[str, binding_argument.ArgumentPath], ...]]:
        """Group nested reference IDs by resource prefix."""
        return {
            prefix: tuple(
                (reference.identifier, path)
                for reference, path in self.references_with_paths
                if reference.prefix == prefix and reference.identifier is not None
            )
            for prefix in selectors.STRUCTURAL_PREFIXES
        }

    @functools.cached_property
    def profile_dataframe_references(self) -> tuple[str, ...]:
        """Return ordered profile data references from all arguments."""
        return tuple(
            identifier
            for argument in self.args.values()
            for identifier in argument.profile_dataframe_references
        )

    @property
    def inferred_feature_inputs(self) -> tuple[str, ...]:
        """Return ordered unique feature inputs inferred by the arguments."""
        return tuple(
            dict.fromkeys(
                feature
                for argument in self.args.values()
                for feature in argument.inferred_feature_inputs
            )
        )

    def profile_dependencies(self, current_profile_id: str) -> list[str]:
        """Aggregate unique inferred profile-data dependencies."""
        return list(
            dict.fromkeys(
                dependency
                for argument in self.args.values()
                for dependency in argument.profile_dependencies(current_profile_id)
            )
        )

    def resolve_args(
        self,
        profile_id: str,
        feature_id: str | None = None,
        grain_keys_by_profile: typing.Mapping[str, typing.Sequence[str]] | None = None,
        resources: binding_argument.BindingResources | None = None,
        *,
        row_context: row_context_values.RowContext | None = None,
    ) -> dict[str, object]:
        """Resolve all arguments with a shared invocation context."""
        return {
            name: argument.resolve(
                profile_id,
                feature_id,
                grain_keys_by_profile,
                resources,
                row_context=row_context,
            )
            for name, argument in self.args.items()
        }
